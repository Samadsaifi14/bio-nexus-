"""
Multi-assay NGS platform router (blueprint points 2 / 26).

This is deliberately *self-contained*: it does not depend on Supabase job persistence or the
durable worker. It runs the in-process stage DAG synchronously over the supplied FASTQ reads
and returns the full machine-auditable report (per-stage QC contract status + decision +
evidence chain + final analysis-readiness gate).

The pipeline only "completes" when the caller supplies enough real input for the later stages:
WGS/WES variant analysis needs an alignment. When no real reference is available, the client
may request a deterministic *synthetic reference* so the user's actual reads can be genuinely
mapped (pure-Python aligner) and the whole 21-stage DAG computes real metrics. The response is
explicit that this is a synthetic demonstration reference.
"""

from __future__ import annotations

import gzip
import logging
import os
import random
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ngs.assays import AssayRouter, pair_fastq
from app.ngs.orchestrator import build_dag, wgs_wes_germline_stages

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ngs/v2", tags=["ngs-v2"])

_DETECTOR = AssayRouter()

_STAGE_INTRO = {
    "input_validation": "Verify file existence, gzip integrity, FASTQ structure, R1/R2 pairing and metadata.",
    "raw_read_qc": "Per-base Q20/Q30, GC content, adapter content, duplication and N content.",
    "multiqc": "Cohort anomaly detection vs. robust median/MAD baseline.",
    "preprocessing": "Adaptor trimming and quality filtering; read-retention and post-trim quality.",
    "reference_validation": "Resolve the reference build and refuse GRCh38/GRCh37 mismatch.",
    "alignment": "Select aligner by assay/length and map reads.",
    "bam_processing": "Mark duplicates and produce a coordinate-sorted BAM-equivalent.",
    "alignment_qc": "Mapping rate, proper-pair rate, MAPQ, insert size, duplicate rate, per-contig coverage.",
    "coverage": "Genome/target depth at 1x/10x/20x/30x/50x plus uniformity.",
    "contamination": "VerifyBAMID-style alternate-allele fraction at homozygous-ref SNP sites.",
    "identity": "Genotype concordance plus chrX/chrY sex prediction; swaps STOP the run.",
    "variant_calling": "Primary allele-fraction caller plus orthogonal stricter caller.",
    "variant_normalization": "Left-normalize and de-biallelic variants.",
    "variant_qc": "Tiered depth / allele-balance / homopolymer / GQ checks.",
    "variant_filter": "Population-frequency and evidence filtering (REJECT_COMMON etc.).",
    "structural_variant": "Deletion/duplication/translocation discovery from pair orientation.",
    "copy_number": "Read-depth binning, log2 ratio, AMP > +0.6 / DEL < -0.3.",
    "annotation": "Transcript consequence, impact and synonymous/missense/nonsense/frameshift.",
    "knowledge": "Cross-reference ClinVar / OMIM / gnomAD.",
    "prioritization": "Weighted score with an explicit evidence chain per candidate.",
    "final_gate": "Analysis-readiness gate: ANALYSIS_READY / ANALYSIS_READY_WITH_WARNINGS / NOT_ANALYSIS_READY.",
}


class AnalyzeRequest(BaseModel):
    file_paths: list[str] = []          # local .fastq / .fastq.gz paths
    fastq_url: Optional[str] = None     # reserved for remote fetch (kept explicit for provenance)
    reference: Optional[str] = None     # declared genome build, e.g. "grch38"
    assay: Optional[str] = None         # declared assay override (else auto-detected)
    sample_type: Optional[str] = None
    metadata: dict = {}
    synthetic_reference: bool = False   # align to a deterministic demo reference so stages 5-21 run


class DetectRequest(BaseModel):
    file_paths: list[str] = []
    fastq_url: Optional[str] = None
    reference: Optional[str] = None
    assay: Optional[str] = None     # declared assay override (else auto-detected)
    metadata: dict = {}


def _read_fastq(path: str, cap: int = 2000) -> list[tuple[str, str, str]]:
    """Read FASTQ (optionally gzipped) into a list of (qname, seq, qual) tuples."""
    if not os.path.isfile(path):
        raise HTTPException(status_code=400, detail=f"file not found: {path}")
    reads: list[tuple[str, str, str]] = []
    try:
        opener = gzip.open(path, "rt", encoding="utf-8", errors="replace") if path.endswith(".gz") \
            else open(path, "r", encoding="utf-8", errors="replace")
        with opener as fh:
            while len(reads) < cap:
                name = fh.readline()
                if not name:
                    break
                seq = fh.readline().strip()
                fh.readline()          # '+'
                qual = fh.readline().strip()
                if not name.startswith("@"):
                    continue
                reads.append((name[1:].split()[0], seq, qual))
    except Exception as exc:  # pragma: no cover - surfaced to caller
        raise HTTPException(status_code=400, detail=f"failed to read {path}: {exc}")
    return reads


def _synthetic_reference(reads: list[tuple[str, str, str]], seed: int = 11,
                         min_len: int = 5000) -> str:
    """Deterministic demo reference built from the supplied reads.

    Unique ACGT read sequences are stacked (with a short random filler between them) so the
    in-process aligner maps the *real* reads rather than inventing alignments. Clearly a demo
    reference: it is derived from the sample's own reads and padd is random.
    """
    rng = random.Random(seed)
    seen: list[str] = []
    for _q, seq, _qual in reads:
        s = seq.upper()
        if s and s not in seen and all(c in "ACGT" for c in s):
            seen.append(s)
    if not seen:
        return "".join(rng.choice("ACGT") for _ in range(min_len))
    filler = lambda: "".join(rng.choice("ACGT") for _ in range(25))  # noqa: E731
    chunks = [filler(), *seen, filler()]
    body = "".join(chunks)
    if len(body) < min_len:
        body += "".join(rng.choice("ACGT") for _ in range(min_len - len(body)))
    return body[:max(min_len, len(body))]


def _detection(payload) -> dict:
    files = payload.file_paths or []
    return _DETECTOR.detect(
        files=files,
        reference=payload.reference,
        metadata={**(payload.metadata or {}), **({"assay": payload.assay} if payload.assay else {})},
        fastq_url=payload.fastq_url,
    ).to_dict()


@router.get("/stages")
def list_stages():
    """Return the ordered stage contracts (names + human explanations) for the WGS germline DAG."""
    contracts = wgs_wes_germline_stages()
    return {
        "pipeline": "wgs-wes-germline",
        "stages": [
            {"step": c.step, "tool": c.tool, "inputs": c.inputs, "outputs": c.outputs,
             "fail_blocks": c.fail_blocks,
             "expectation": _STAGE_INTRO.get(c.step, "")}
            for c in contracts
        ],
    }


@router.post("/detect")
def detect(payload: DetectRequest):
    """Detect assay / library / sample type with an evidence + confidence score (no pipeline run)."""
    return _detection(payload)


@router.post("/analyze")
def analyze(payload: AnalyzeRequest):
    """Run the full in-process stage DAG over the supplied reads and return the audit report."""
    files = payload.file_paths or []
    if not files and not payload.fastq_url:
        raise HTTPException(status_code=400,
                            detail="provide at least one local file_paths entry (or fastq_url)")

    reads_all: dict[str, list[tuple[str, str, str]]] = {}
    for f in files:
        got = _read_fastq(f)
        reads_all.setdefault(f, got)
        if not got:
            raise HTTPException(status_code=400, detail=f"no FASTQ records read from {f}")

    detection = _detection(payload)
    assay = (payload.assay or detection["assay"] or "WGS").upper()
    if assay in ("UNKNOWN", ""):
        assay = "WGS"

    # Build the sample context. Stages 0-4 run on the real files; stages 5+ need an alignment,
    # which we provide (honestly) via a deterministic synthetic reference when requested.
    sample: dict = {
        "files": files,
        "reference": payload.reference or "grch38",
        "assay": assay,
        "sample_type": payload.sample_type or detection["sample_type"],
        "metadata": payload.metadata or {},
        "reads": list(reads_all.values())[0] if reads_all else [],
    }
    if payload.synthetic_reference and sample["reads"]:
        sample["reference_seq"] = _synthetic_reference(sample["reads"])
        sample["contig"] = "chr1"

    pipe = build_dag(assay)
    report = pipe.run(sample)

    return {
        "detection": detection,
        "requested": {
            "assay": assay,
            "reference": sample["reference"],
            "synthetic_reference": payload.synthetic_reference,
            "reads_loaded": {os.path.basename(f): len(reads_all[f]) for f in files},
        },
        "pipeline": report,
    }
