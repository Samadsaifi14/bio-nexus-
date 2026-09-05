import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional

from app.services.ncbi_service import NCBIService
from app.tools.oligo_qc import clean, is_dna, oligo_report, dimer_analysis, in_silico_pcr
from app.tools.primer_advanced import multiplex_compatibility, snp_overlap

router = APIRouter(prefix="/api/primers", tags=["primers"])
ncbi_service = NCBIService()

try:
    import primer3
    HAS_PRIMER3 = True
except ImportError:
    HAS_PRIMER3 = False


class PrimerRequest(BaseModel):
    sequence: str
    product_size_min: int = Field(default=100, ge=50)
    product_size_max: int = Field(default=500, le=2000)
    opt_tm: float = Field(default=60.0)
    num_return: int = Field(default=5, ge=1, le=10)
    gc_min: float = Field(default=40.0)
    gc_max: float = Field(default=65.0)


class PrimerPair(BaseModel):
    pair_index: int
    left_seq: str
    left_tm: float
    left_gc: float
    left_pos: int
    left_len: int
    right_seq: str
    right_tm: float
    right_gc: float
    right_pos: int
    right_len: int
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
    seq_args = {"SEQUENCE_ID": "target", "SEQUENCE_TEMPLATE": seq}
    global_args = {
        "PRIMER_OPT_SIZE": 20,
        "PRIMER_MIN_SIZE": 18,
        "PRIMER_MAX_SIZE": 25,
        "PRIMER_OPT_TM": req.opt_tm,
        "PRIMER_MIN_TM": req.opt_tm - 3,
        "PRIMER_MAX_TM": req.opt_tm + 3,
        "PRIMER_MIN_GC": req.gc_min,
        "PRIMER_MAX_GC": req.gc_max,
        "PRIMER_PRODUCT_SIZE_RANGE": [[req.product_size_min, req.product_size_max]],
        "PRIMER_NUM_RETURN": req.num_return,
        "PRIMER_EXPLAIN_FLAG": 1,
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
            pair_index=i,
            left_seq=result.get(f"PRIMER_LEFT_{i}_SEQUENCE", ""),
            left_tm=result.get(f"PRIMER_LEFT_{i}_TM", 0),
            left_gc=result.get(f"PRIMER_LEFT_{i}_GC_PERCENT", 0),
            left_pos=lp[0],
            left_len=lp[1],
            right_seq=result.get(f"PRIMER_RIGHT_{i}_SEQUENCE", ""),
            right_tm=result.get(f"PRIMER_RIGHT_{i}_TM", 0),
            right_gc=result.get(f"PRIMER_RIGHT_{i}_GC_PERCENT", 0),
            right_pos=rp[0],
            right_len=rp[1],
            product_size=result.get(f"PRIMER_PAIR_{i}_PRODUCT_SIZE", 0),
            penalty=result.get(f"PRIMER_PAIR_{i}_PENALTY", 0),
        ))
    if not pairs:
        raise HTTPException(404, "No primer pairs found. Try relaxing GC%, Tm, or product size constraints.")
    return pairs


def _record_type(accession: str) -> str:
    acc = (accession or "").upper()
    if acc.startswith(("NM_", "XM_")):
        return "mRNA"
    if acc.startswith(("NR_", "XR_")):
        return "non-coding RNA"
    if acc.startswith("NG_"):
        return "genomic DNA"
    if acc.startswith("NC_"):
        return "chromosome"
    if acc.startswith(("NT_", "NW_", "AC_", "AE_")):
        return "genomic (assembly)"
    return "nucleotide"


class PrimerSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    max_results: int = Field(12, ge=1, le=50)


_ORGANISM_HINTS = {
    "human": "Homo sapiens", "homo sapiens": "Homo sapiens",
    "mouse": "Mus musculus", "mus musculus": "Mus musculus",
    "rat": "Rattus norvegicus", "rattus norvegicus": "Rattus norvegicus",
    "zebrafish": "Danio rerio", "danio rerio": "Danio rerio",
    "fly": "Drosophila melanogaster", "drosophila": "Drosophila melanogaster",
    "yeast": "Saccharomyces cerevisiae", "saccharomyces cerevisiae": "Saccharomyces cerevisiae",
    "worm": "Caenorhabditis elegans", "c elegans": "Caenorhabditis elegans",
    "e coli": "Escherichia coli", "escherichia coli": "Escherichia coli",
    "arabidopsis": "Arabidopsis thaliana", "plant": "Arabidopsis thaliana",
    "bovine": "Bos taurus", "cow": "Bos taurus", "dog": "Canis lupus familiaris", "pig": "Sus scrofa",
}


def _build_nucleotide_query(term: str) -> str:
    term = term.strip()
    if not term or "[" in term:
        return term
    first = term.split()[0].upper()
    if re.match(r"^(NM_|XM_|NR_|XR_|NG_|NC_|NT_|NW_|AC_|AE_|AF_|AY_)", first):
        return f"{term.strip()}[ACCN]"
    tokens = [t for t in term.split() if t]
    gene = tokens[0]
    for i, tok in enumerate(tokens[1:], start=1):
        hint = _ORGANISM_HINTS.get(tok.lower())
        if hint:
            organism = hint
            extra = " ".join(t for t in tokens[1:i] + tokens[i + 1:] if t)
            break
    else:
        organism = None
        extra = " ".join(tokens[1:])
    parts = [f"{gene}[Gene Name]"]
    if extra:
        parts.append(extra)
    if organism:
        parts.append(f"{organism}[Organism]")
    return " AND ".join(parts)


def _result_priority(r: dict) -> int:
    rt = r.get("record_type", "")
    title = r.get("title", "").lower()
    if "complete cds" in title and rt == "mRNA": return 0
    if "complete cds" in title: return 1
    if rt == "mRNA": return 2
    if rt == "genomic DNA": return 3
    if rt == "non-coding RNA": return 4
    return 5


@router.post("/search")
async def search_primer_targets(req: PrimerSearchRequest):
    query = _build_nucleotide_query(req.query)
    result = await ncbi_service.search_by_name(query, db="nucleotide", max_results=req.max_results)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    for r in result["results"]:
        r["record_type"] = _record_type(r.get("accession", ""))
        r["suggested_use"] = "ideal" if r["record_type"] == "mRNA" else "ok"
    result["results"].sort(key=_result_priority)
    result["query"] = req.query
    result["ncbi_query"] = query
    return result


class PrimerAnalyzeRequest(BaseModel):
    left_seq: str = Field(..., min_length=5)
    right_seq: str = Field(..., min_length=5)
    template: Optional[str] = None
    left_pos: Optional[int] = None
    right_pos: Optional[int] = None
    expected_product: Optional[int] = Field(None, ge=1)
    variants: list[dict[str, Any]] = Field(default_factory=list, description="0-based template variant coordinates for SNP/variant overlap screening")


@router.post("/analyze")
async def analyze_primer(req: PrimerAnalyzeRequest):
    left = clean(req.left_seq)
    right = clean(req.right_seq)
    if not is_dna(left) or not is_dna(right):
        raise HTTPException(400, "Primers must be DNA (A/T/G/C/N only).")
    if len(left) < 5 or len(right) < 5:
        raise HTTPException(400, "Primers must be at least 5 bases.")
    qc = {"left": oligo_report(left), "right": oligo_report(right), "hetero_dimer": dimer_analysis(left, right)}
    response: dict[str, Any] = {"qc": qc}
    if req.template:
        template = clean(req.template)
        if not template:
            raise HTTPException(400, "Template sequence is required for in-silico PCR.")
        response["pcr"] = in_silico_pcr(template, left, right, expected_product=req.expected_product, left_expected=req.left_pos, right_expected=req.right_pos)
    if req.variants:
        if req.left_pos is None or req.right_pos is None:
            response["snp_overlap"] = {"status": "unavailable", "reason": "Primer3 left_pos and right_pos are required to map variants."}
        else:
            response["snp_overlap"] = snp_overlap(left, right, req.left_pos, req.right_pos, req.variants)
    try:
        from app.ai.tool_interpreter import interpret_tool_result
        ai_interp = await interpret_tool_result("primers", response)
        if ai_interp:
            response["ai_interpretation"] = ai_interp
    except Exception:
        pass
    return response


class MultiplexRequest(BaseModel):
    pairs: list[dict[str, Any]] = Field(..., min_length=2)
    max_tm_spread_c: float = Field(3.0, ge=0.5, le=10.0)


@router.post("/multiplex")
async def analyze_multiplex(req: MultiplexRequest):
    """Screen multiple primer pairs for Tm spread and cross-primer dimers."""
    try:
        return multiplex_compatibility(req.pairs, req.max_tm_spread_c)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
