"""Sequence-tool endpoints: one authoritative sequence library plus motif/dotplot tools."""

from __future__ import annotations

import logging
from typing import Any, Literal

import Bio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.science.result import build_scientific_result
from app.tools.sequence_utilities import (
    SequenceUtilitiesError,
    analyze_sequence,
    clean_sequence,
    complement_sequence,
    find_orfs,
    format_fasta,
    reverse_complement_sequence,
    reverse_sequence,
    transcribe_dna,
    translate_cds,
    translate_selected_frame,
)
from app.tools.motif_scanner import (
    MotifError,
    get_motif_patterns,
    list_motif_categories,
    scan_library,
    scan_pattern,
)
from app.tools.dotplot import DotPlotError, compute_dotplot
from app.tools.alignment_insights import alignment_insights

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/seq-tools", tags=["sequence-tools"])


class AnalyzeRequest(BaseModel):
    sequence: str = Field(..., min_length=1, description="Raw sequence or FASTA (DNA/RNA/protein)")
    seq_type: str = Field("auto", description="auto|dna|rna|protein — force interpretation")


class TranslationFrames(BaseModel):
    frames: dict[str, str]
    best: dict[str, Any] | None = None
    genetic_code: str | None = None
    frame_convention: str | None = None


class RestrictionSite(BaseModel):
    name: str
    recognition: str
    count: int
    positions: list[int]


class AaComposition(BaseModel):
    aa: str
    count: int
    pct: float


class AnalyzeResponse(BaseModel):
    sequence_type: str
    detected_type: str
    length: int
    gc_content: float | None = None
    molecular_weight: float | None = None
    molecular_weight_assumptions: str | None = None
    reverse_complement: str | None = None
    transcription: str | None = None
    translation: TranslationFrames | None = None
    aa_composition: list[AaComposition] | None = None
    restriction_sites: list[RestrictionSite] | None = None
    issues: list[str]


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_sequence_endpoint(req: AnalyzeRequest):
    """Legacy-shaped response backed by the same validated library as /operate."""
    try:
        return analyze_sequence(req.sequence, req.seq_type)
    except SequenceUtilitiesError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class SequenceOperationRequest(BaseModel):
    sequence: str = Field(..., min_length=1)
    seq_type: str = Field("auto", description="auto|dna|rna|protein")
    operation: Literal[
        "analyze",
        "reverse_complement",
        "complement",
        "reverse",
        "transcribe",
        "translate_frame",
        "find_orfs",
        "translate_cds",
        "fasta",
    ] = "analyze"
    frame: int = Field(1, ge=-3, le=3)
    stop_at_stop: bool = False
    require_start: bool = False
    require_terminal_stop: bool = False
    min_orf_aa: int = Field(1, ge=1, le=100000)
    fasta_name: str = "sequence"
    fasta_width: int = Field(60, ge=1, le=1000)


@router.post("/operate")
async def operate_sequence(req: SequenceOperationRequest):
    """ScientificResult endpoint used by Utility Tools; no client-side biology."""
    try:
        analysis = analyze_sequence(req.sequence, req.seq_type)
        effective = analysis["sequence_type"]
        if req.frame == 0:
            raise SequenceUtilitiesError("frame cannot be 0; choose 1, 2, 3, -1, -2 or -3")

        if req.operation == "analyze":
            operation_result: Any = analysis
        elif req.operation == "reverse_complement":
            operation_result = reverse_complement_sequence(req.sequence, effective)
        elif req.operation == "complement":
            operation_result = complement_sequence(req.sequence, effective)
        elif req.operation == "reverse":
            operation_result = reverse_sequence(req.sequence, effective)
        elif req.operation == "transcribe":
            if effective != "dna":
                raise SequenceUtilitiesError("Transcription requires DNA input")
            operation_result = transcribe_dna(req.sequence)
        elif req.operation == "translate_frame":
            operation_result = translate_selected_frame(
                req.sequence,
                seq_type=effective,
                frame=req.frame,
                stop_at_stop=req.stop_at_stop,
            )
        elif req.operation == "find_orfs":
            operation_result = find_orfs(req.sequence, seq_type=effective, min_aa=req.min_orf_aa)
        elif req.operation == "translate_cds":
            operation_result = translate_cds(
                req.sequence,
                seq_type=effective,
                frame=req.frame,
                require_start=req.require_start,
                require_terminal_stop=req.require_terminal_stop,
            )
        elif req.operation == "fasta":
            operation_result = format_fasta(
                req.sequence,
                effective,
                name=req.fasta_name,
                width=req.fasta_width,
            )
        else:  # pragma: no cover - Literal guards this
            raise SequenceUtilitiesError("Unsupported sequence operation")

        parameters = {
            "seq_type": effective,
            "operation": req.operation,
            "frame": req.frame if req.operation in {"translate_frame", "translate_cds"} else None,
            "stop_at_stop": req.stop_at_stop if req.operation == "translate_frame" else None,
            "require_start": req.require_start if req.operation == "translate_cds" else None,
            "require_terminal_stop": req.require_terminal_stop if req.operation == "translate_cds" else None,
            "min_orf_aa": req.min_orf_aa if req.operation == "find_orfs" else None,
        }
        return build_scientific_result(
            status="VALID",
            method=f"sequence utility: {req.operation}",
            engine="BioNexus sequence library (Biopython-backed)",
            engine_version=Bio.__version__,
            input_payload={"sequence": req.sequence, "parameters": parameters},
            parameters=parameters,
            results={
                "operation": req.operation,
                "sequence_type": effective,
                "input_length": analysis["length"],
                "value": operation_result,
            },
            evidence_class="Deterministic computation",
            validation={
                "strict_invalid_character_rejection": True,
                "iupac_preserved": True,
                "client_side_scientific_calculation": False,
            },
            citations=[{"label": "Biopython", "url": "https://biopython.org/"}],
        )
    except SequenceUtilitiesError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class PatternScanRequest(BaseModel):
    sequence: str = Field(..., min_length=1, description="Protein sequence (raw or FASTA)")
    pattern: str = Field(..., min_length=1, description="PROSITE pattern, e.g. [ST]-x-[RK]")


class LibraryScanRequest(BaseModel):
    sequence: str = Field(..., min_length=1, description="Protein sequence (raw or FASTA)")
    categories: list[str] | None = Field(None, description="Optional category filter")


class MotifMatch(BaseModel):
    start: int
    end: int
    motif: str


class PatternScanResponse(BaseModel):
    sequence_type: str
    pattern: str
    regex: str
    count: int
    matches: list[MotifMatch]


class LibraryHit(BaseModel):
    name: str
    accession: str = ""
    category: str = ""
    specificity: str = "loose"
    description: str
    pattern: str
    count: int
    matches: list[MotifMatch]


class LibraryScanResponse(BaseModel):
    sequence_type: str
    length: int
    patterns_scanned: int
    motifs_found: int
    hits: list[LibraryHit]


@router.post("/motif-scan", response_model=PatternScanResponse)
async def scan_custom_pattern(req: PatternScanRequest):
    try:
        return scan_pattern(req.sequence, req.pattern)
    except MotifError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/motif-library", response_model=LibraryScanResponse)
async def scan_motif_library(req: LibraryScanRequest):
    try:
        return scan_library(req.sequence, categories=req.categories)
    except MotifError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/motif-library/patterns")
async def list_motif_patterns_endpoint():
    return get_motif_patterns()


@router.get("/motif-library/categories")
async def list_motif_categories_endpoint():
    return list_motif_categories()


class DotPlotRequest(BaseModel):
    seq_a: str = Field(..., min_length=1)
    seq_b: str = Field(..., min_length=1)
    window: int = Field(10, ge=1, le=200)
    stringency: int = Field(80, ge=1, le=100)
    scoring: str = Field("identity")


class DotPlotFeatures(BaseModel):
    main_diagonal_pct: float
    gaps: dict[str, int]
    off_diagonal: list[dict[str, int]]
    anti_diagonal: list[dict[str, int]]


class DotPlotResponse(BaseModel):
    sequence_type: str
    seq_a_length: int
    seq_b_length: int
    window: int
    stringency: int
    scoring: str
    scoring_used: str
    threshold: int
    total_matches: int
    dot_count: int
    downsampled: bool
    features: DotPlotFeatures
    dots: list[list[int]]


@router.post("/dotplot", response_model=DotPlotResponse)
async def run_dotplot(req: DotPlotRequest):
    try:
        return compute_dotplot(req.seq_a, req.seq_b, window=req.window, stringency=req.stringency, scoring=req.scoring)
    except DotPlotError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class AlignmentInsightsRequest(BaseModel):
    aligned_sequences: list[str] = Field(..., min_length=2, description="Already aligned sequences of equal length; gaps use '-' or '.'")
    reference_index: int = Field(0, ge=0)
    variants: list[dict[str, Any]] = Field(default_factory=list, description="Optional variants with a 1-based ungapped reference 'position'")


@router.post("/alignment-insights")
async def analyze_alignment_insights(req: AlignmentInsightsRequest):
    try:
        return alignment_insights(req.aligned_sequences, req.reference_index, req.variants)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
