"""
Multi-assay NGS platform router.

The v2 route runs a self-contained, auditable stage DAG and returns per-stage QC contracts,
evidence, provenance, visualization data and a final analysis-readiness gate.

For product evaluation and teaching, the router can also generate deterministic demonstration
FASTQ pairs. Demo datasets are explicitly labelled in the response and still pass through the
same FASTQ reader, QC stages, alignment logic and final gate as user-supplied files.
"""

from __future__ import annotations

import gzip
import logging
import os
import random
import tempfile
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ngs.assays import AssayRouter
from app.ngs.orchestrator import build_dag, wgs_wes_germline_stages
from app.ngs.visualization import build_visualization

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

_DEMO_PROFILES = {
    "wgs-clean": {
        "label": "Clean paired-end WGS",
        "assay": "WGS",
        "description": "High-quality 2x150 bp Illumina-like reads intended to exercise the complete 21-stage DAG.",
        "read_pairs": 180,
        "low_quality_fraction": 0.0,
        "duplicate_fraction": 0.03,
    },
    "wgs-mixed-quality": {
        "label": "Mixed-quality WGS",
        "assay": "WGS",
        "description": "Paired-end reads with a low-quality tail and modest duplicate burden to demonstrate WARN states.",
        "read_pairs": 180,
        "low_quality_fraction": 0.22,
        "duplicate_fraction": 0.12,
    },
    "wes-small": {
        "label": "Compact WES demo",
        "assay": "WES",
        "description": "Compact paired-end exome-style demonstration dataset for fast UI testing.",
        "read_pairs": 120,
        "low_quality_fraction": 0.05,
        "duplicate_fraction": 0.08,
    },
}


class AnalyzeRequest(BaseModel):
    file_paths: list[str] = []
    fastq_url: Optional[str] = None
    reference: Optional[str] = None
    assay: Optional[str] = None
    sample_type: Optional[str] = None
    metadata: dict = {}
    synthetic_reference: bool = False
    demo_profile: Optional[str] = None


class DetectRequest(BaseModel):
    file_paths: list[str] = []
    fastq_url: Optional[str] = None
    reference: Optional[str] = None
    assay: Optional[str] = None
    metadata: dict = {}


def _read_fastq(path: str, cap: int = 2000) -> list[tuple[str, str, str]]:
    if not os.path.isfile(path):
        raise HTTPException(status_code=400, detail=f"file not found: {path}")
    reads: list[tuple[str, str, str]] = []
    try:
        opener = gzip.open(path, "rt", encoding="utf-8", errors="replace") if path.endswith(".gz") else open(path, "r", encoding="utf-8", errors="replace")
        with opener as fh:
            while len(reads) < cap:
                name = fh.readline()
                if not name:
                    break
                seq = fh.readline().strip()
                plus = fh.readline().strip()
                qual = fh.readline().strip()
                if not name.startswith("@") or not plus.startswith("+"):
                    continue
                reads.append((name[1:].split()[0], seq, qual))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"failed to read {path}: {exc}")
    return reads


def _demo_sequence(rng: random.Random, length: int = 150) -> str:
    return "".join(rng.choice("ACGT") for _ in range(length))


def _write_demo_fastqs(profile_name: str) -> tuple[list[str], dict]:
    if profile_name not in _DEMO_PROFILES:
        raise HTTPException(status_code=400, detail=f"unknown demo_profile: {profile_name}")
    profile = _DEMO_PROFILES[profile_name]
    rng = random.Random(20260830 + list(_DEMO_PROFILES).index(profile_name))
    directory = tempfile.mkdtemp(prefix=f"bionexus-{profile_name}-")
    r1_path = os.path.join(directory, f"BN_DEMO_{profile['assay']}_R1.fastq")
    r2_path = os.path.join(directory, f"BN_DEMO_{profile['assay']}_R2.fastq")
    unique_pairs: list[tuple[str, str]] = []
    duplicate_fraction = float(profile["duplicate_fraction"])
    low_quality_fraction = float(profile["low_quality_fraction"])
    n_pairs = int(profile["read_pairs"])
    with open(r1_path, "w", encoding="utf-8") as r1, open(r2_path, "w", encoding="utf-8") as r2:
        for i in range(n_pairs):
            duplicate = bool(unique_pairs) and rng.random() < duplicate_fraction
            if duplicate:
                seq1, seq2 = rng.choice(unique_pairs)
            else:
                seq1, seq2 = _demo_sequence(rng), _demo_sequence(rng)
                unique_pairs.append((seq1, seq2))
            low_quality = rng.random() < low_quality_fraction
            if low_quality:
                qual1 = "I" * 100 + "+" * 50
                qual2 = "I" * 95 + "+" * 55
            else:
                qual1 = "I" * len(seq1)
                qual2 = "I" * len(seq2)
            qname = f"BNDEMO:{profile_name}:{i:05d}"
            r1.write(f"@{qname}/1\n{seq1}\n+\n{qual1}\n")
            r2.write(f"@{qname}/2\n{seq2}\n+\n{qual2}\n")
    return [r1_path, r2_path], {
        "profile": profile_name,
        "label": profile["label"],
        "description": profile["description"],
        "synthetic": True,
        "read_pairs": n_pairs,
    }


def _synthetic_reference(reads: list[tuple[str, str, str]], seed: int = 11, min_len: int = 5000) -> str:
    rng = random.Random(seed)
    seen: list[str] = []
    for _q, seq, _qual in reads:
        s = seq.upper()
        if s and s not in seen and all(c in "ACGT" for c in s):
            seen.append(s)
    if not seen:
        return "".join(rng.choice("ACGT") for _ in range(min_len))
    filler = lambda: "".join(rng.choice("ACGT") for _ in range(25))  # noqa: E731
    body = "".join([filler(), *seen, filler()])
    if len(body) < min_len:
        body += "".join(rng.choice("ACGT") for _ in range(min_len - len(body)))
    return body[:max(min_len, len(body))]


def _detection(payload, files: Optional[list[str]] = None) -> dict:
    chosen_files = files if files is not None else (payload.file_paths or [])
    return _DETECTOR.detect(
        files=chosen_files,
        reference=payload.reference,
        metadata={**(payload.metadata or {}), **({"assay": payload.assay} if payload.assay else {})},
        fastq_url=payload.fastq_url,
    ).to_dict()


@router.get("/stages")
def list_stages():
    contracts = wgs_wes_germline_stages()
    return {"pipeline": "wgs-wes-germline", "stages": [
        {"step": c.step, "tool": c.tool, "inputs": c.inputs, "outputs": c.outputs,
         "fail_blocks": c.fail_blocks, "expectation": _STAGE_INTRO.get(c.step, "")}
        for c in contracts
    ]}


@router.get("/demos")
def list_demos():
    return {"demos": [{"id": key, **value} for key, value in _DEMO_PROFILES.items()]}


@router.post("/detect")
def detect(payload: DetectRequest):
    return _detection(payload)


@router.post("/analyze")
def analyze(payload: AnalyzeRequest):
    files = list(payload.file_paths or [])
    demo: Optional[dict] = None
    if payload.demo_profile:
        files, demo = _write_demo_fastqs(payload.demo_profile)
    if not files and not payload.fastq_url:
        raise HTTPException(status_code=400, detail="provide file_paths, fastq_url, or demo_profile")

    reads_all: dict[str, list[tuple[str, str, str]]] = {}
    for f in files:
        got = _read_fastq(f)
        reads_all[f] = got
        if not got:
            raise HTTPException(status_code=400, detail=f"no FASTQ records read from {f}")

    detection = _detection(payload, files=files)
    demo_assay = _DEMO_PROFILES[payload.demo_profile]["assay"] if payload.demo_profile else None
    assay = (payload.assay or demo_assay or detection["assay"] or "WGS").upper()
    if assay in ("UNKNOWN", ""):
        assay = "WGS"

    combined_reads = [read for f in files for read in reads_all.get(f, [])]
    sample: dict = {
        "files": files,
        "reference": payload.reference or "grch38",
        "assay": assay,
        "sample_type": payload.sample_type or detection["sample_type"],
        "metadata": {**(payload.metadata or {}), **({"demo_profile": payload.demo_profile} if payload.demo_profile else {})},
        "demonstration_data": bool(payload.demo_profile or (payload.metadata or {}).get("demonstration_data")),
        "synthetic_reference": bool(payload.synthetic_reference or payload.demo_profile),
        "reads": combined_reads,
    }
    use_synthetic_reference = sample["synthetic_reference"]
    if use_synthetic_reference and combined_reads:
        sample["reference_seq"] = _synthetic_reference(combined_reads)
        sample["contig"] = "chr1"

    pipe = build_dag(assay)
    report = pipe.run(sample)
    return {
        "detection": detection,
        "requested": {
            "assay": assay,
            "reference": sample["reference"],
            "synthetic_reference": use_synthetic_reference,
            "demo_profile": payload.demo_profile,
            "reads_loaded": {os.path.basename(f): len(reads_all[f]) for f in files},
            "reads_analyzed": len(combined_reads),
        },
        "demo": demo,
        "pipeline": report,
        "visualization": build_visualization(pipe.state),
    }
