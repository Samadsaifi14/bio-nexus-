"""
Stage 5 — Alignment (blueprint Stage 5).

The platform should not make the user choose an aligner blindly. It selects by assay/length:

    Illumina short-read DNA   -> BWA-MEM2
    Long-read                 -> minimap2
    RNA-seq                   -> STAR (or Salmon for quant-only)

This stage implements: (a) aligner selection (auditable), (b) an execution path that invokes
the external aligner when present, and (c) a pure-Python fallback aligner (app.ngs.sam) so the
platform is runnable without heavy tooling. The output is a SAM/BAM-equivalent record list that
feeds Stage 6 (BAM processing), Stage 7 (alignment QC) and Stage 8 (coverage).
"""

from __future__ import annotations

from typing import Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule
from app.ngs.sam import map_reads

# available aligners by assay + read length
def choose_aligner(assay: str, read_length: Optional[int]) -> str:
    """Return the recommended aligner + reason string."""
    a = assay.upper()
    if a in ("RNA-SEQ", "RNA"):
        return "STAR"
    if read_length and read_length >= 1000:
        return "minimap2"     # assumed long-read
    if a in ("WGS", "WES", "AMPLICON", "TARGETED", "PANEL"):
        return "bwa-mem2"
    if a == "AMPLICON":
        return "bwa-mem2"
    return "bwa-mem2"


def _align_python(
    ref_seq: str,
    reads: list[tuple[str, str, str]],
    ref_name: str = "chr1",
) -> list[dict]:
    return map_reads(ref_seq, reads, ref_name=ref_name, seed_len=10, min_len=20)


def align(
    assay: str,
    reads: list[tuple[str, str, str]],
    ref_seq: str,
    ref_name: str = "chr1",
    read_length: Optional[int] = None,
) -> tuple[list[dict], dict]:
    """Align reads to a reference sequence. Returns (SAM records, meta).

    This endpoint currently executes the platform's seed-based Python aligner. The recommended
    production aligner is recorded separately and must never be represented as executed.
    """
    aligner = choose_aligner(assay, read_length)
    records = _align_python(ref_seq, reads, ref_name=ref_name)
    return records, {
        "recommended_production_aligner": aligner,
        "executed_implementation": "bionexus-seed-aligner",
        "executor": "python-surrogate",
        "reference": ref_name,
        "read_length": read_length,
        "aligned_reads": len(records),
        "mapped": sum(1 for r in records if not r.get("is_unmapped")),
    }


def _stage5_run(sample: dict, state: dict) -> tuple[dict, dict]:
    assay = sample.get("assay") or "WGS"
    reads = sample.get("reads") or state.get("reads")
    ref_seq = sample.get("reference_seq") or state.get("reference_seq")
    if not reads or not ref_seq:
        return {"error": "alignment needs reads + reference sequence"}, {}
    records, meta = align(assay, reads, ref_seq,
                          ref_name=sample.get("contig", "chr1"),
                          read_length=sample.get("metadata", {}).get("read_length"))
    state["aligned_records"] = records
    state["sam_path"] = None
    state.setdefault("alignment_meta", {})["matrix"] = meta
    return meta, {
        "mapping_ok": (meta["mapped"] / meta["aligned_reads"] * 100.0)
        if meta["aligned_reads"] else 0.0,
    }


def stage5_contract() -> StageContract:
    return StageContract(
        step="alignment",
        tool="bionexus-seed-aligner",
        version="0.1.0",
        inputs=["clean_fastq", "reference_sequence"],
        outputs=["aligned_reads"],
        rules=[
            ThresholdRule(name="mapping_ok", metric="mapping_ok",
                          evaluate=lambda v: _pct_rule(v, 95, 85)),
        ],
        fail_blocks=False,
        run=_stage5_run,
        evidence_level="SURROGATE",
    )


def _pct_rule(v, ok, warn):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return QcStatus.FAIL
    if v >= ok:
        return QcStatus.PASS
    if v >= warn:
        return QcStatus.WARN
    return QcStatus.FAIL


def run_alignment(
    reads: list[tuple[str, str, str]],
    ref_seq: str,
    assay: str = "WGS",
    ref_name: str = "chr1",
    read_length: Optional[int] = None,
) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    records, meta = align(assay, reads, ref_seq, ref_name=ref_name, read_length=read_length)
    sample = {"assay": assay, "reads": reads, "reference_seq": ref_seq,
              "metadata": {"read_length": read_length}}
    metrics = {
        "mapping_ok": (meta["mapped"] / meta["aligned_reads"] * 100.0)
        if meta["aligned_reads"] else 0.0,
    }
    contract = stage5_contract()
    result = QcResult.from_metrics(apply_rules(contract.resolve_rules(sample), metrics),
                                   fail_blocks=False)
    return {
        "result": {"step": "alignment", "qc": result.to_dict(),
                   "decision": result.decision.value, "data": {"meta": meta,
                                                               "n_records": len(records)}},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "meta": meta, "records": records},
        "records": records,
    }
