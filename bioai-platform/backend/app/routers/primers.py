from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/primers", tags=["primers"])

try:
    import primer3
    HAS_PRIMER3 = True
except ImportError:
    HAS_PRIMER3 = False

class PrimerRequest(BaseModel):
    sequence: str
    product_size_min: int = Field(default=100, ge=50)
    product_size_max: int = Field(default=500, le=2000)
    opt_tm: float          = Field(default=60.0)
    num_return: int        = Field(default=5, ge=1, le=10)
    gc_min: float          = Field(default=40.0)
    gc_max: float          = Field(default=65.0)

class PrimerPair(BaseModel):
    pair_index: int
    left_seq: str;   left_tm: float;   left_gc: float;   left_pos: int;   left_len: int
    right_seq: str;  right_tm: float;  right_gc: float;  right_pos: int;  right_len: int
    product_size: int
    penalty: float

@router.post("/design", response_model=list[PrimerPair])
async def design_primers(req: PrimerRequest):
    if not HAS_PRIMER3:
        raise HTTPException(503, "Primer3 is not installed on this server")

    seq = req.sequence.upper().replace(" ", "").replace("\n", "")
    if len(seq) < 100:
        raise HTTPException(400, "Sequence must be at least 100 bases for primer design")
    if not all(c in "ATGCN" for c in seq):
        raise HTTPException(400, "Sequence must be DNA (A/T/G/C/N only). Convert protein to CDS first.")

    seq_args = {
        "SEQUENCE_ID":       "target",
        "SEQUENCE_TEMPLATE": seq,
    }
    global_args = {
        "PRIMER_OPT_SIZE":         20,
        "PRIMER_MIN_SIZE":         18,
        "PRIMER_MAX_SIZE":         25,
        "PRIMER_OPT_TM":           req.opt_tm,
        "PRIMER_MIN_TM":           req.opt_tm - 3,
        "PRIMER_MAX_TM":           req.opt_tm + 3,
        "PRIMER_MIN_GC":           req.gc_min,
        "PRIMER_MAX_GC":           req.gc_max,
        "PRIMER_PRODUCT_SIZE_RANGE": [[req.product_size_min, req.product_size_max]],
        "PRIMER_NUM_RETURN":        req.num_return,
        "PRIMER_EXPLAIN_FLAG":      1,
    }

    try:
        result = primer3.bindings.design_primers(seq_args, global_args)
    except Exception as e:
        raise HTTPException(500, f"Primer3 error: {e}")

    pairs: list[PrimerPair] = []
    n = result.get("PRIMER_PAIR_NUM_RETURNED", 0)
    for i in range(n):
        lp = result.get(f"PRIMER_LEFT_{i}")
        rp = result.get(f"PRIMER_RIGHT_{i}")
        if not lp or not rp:
            continue
        pairs.append(PrimerPair(
            pair_index   = i,
            left_seq     = result.get(f"PRIMER_LEFT_{i}_SEQUENCE", ""),
            left_tm      = result.get(f"PRIMER_LEFT_{i}_TM", 0),
            left_gc      = result.get(f"PRIMER_LEFT_{i}_GC_PERCENT", 0),
            left_pos     = lp[0],
            left_len     = lp[1],
            right_seq    = result.get(f"PRIMER_RIGHT_{i}_SEQUENCE", ""),
            right_tm     = result.get(f"PRIMER_RIGHT_{i}_TM", 0),
            right_gc     = result.get(f"PRIMER_RIGHT_{i}_GC_PERCENT", 0),
            right_pos    = rp[0],
            right_len    = rp[1],
            product_size = result.get(f"PRIMER_PAIR_{i}_PRODUCT_SIZE", 0),
            penalty      = result.get(f"PRIMER_PAIR_{i}_PENALTY", 0),
        ))
    if not pairs:
        raise HTTPException(404, "No primer pairs found. Try relaxing GC%, Tm, or product size constraints.")
    return pairs
