"""Sequence-tool endpoints: utilities, motif scanner, dot plot and MSA insights."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.tools.sequence_utilities import SequenceUtilitiesError, analyze_sequence
from app.tools.motif_scanner import (
    MotifError,
    get_motif_patterns,
    list_motif_categories,
    scan_library,
    scan_pattern,
)
from app.tools.dotplot import DotPlotError, SCORING_OPTIONS, compute_dotplot
from app.tools.alignment_insights import alignment_insights

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/seq-tools", tags=["sequence-tools"])


class AnalyzeRequest(BaseModel):
    sequence: str = Field(..., min_length=1, description="Raw sequence or FASTA (DNA/RNA/protein)")
    seq_type: str = Field("auto", description="auto|dna|rna|protein — force interpretation")


class TranslationFrames(BaseModel):
    frames: dict[str, str]
    best: dict[str, Any] | None = None


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
    reverse_complement: str | None = None
    translation: TranslationFrames | None = None
    aa_composition: list[AaComposition] | None = None
    restriction_sites: list[RestrictionSite] | None = None
    issues: list[str]


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_sequence_endpoint(req: AnalyzeRequest):
    try:
        return analyze_sequence(req.sequence, req.seq_type)
    except SequenceUtilitiesError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    except MotifError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/motif-library", response_model=LibraryScanResponse)
async def scan_motif_library(req: LibraryScanRequest):
    try:
        return scan_library(req.sequence, categories=req.categories)
    except MotifError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/motif-library/patterns")
async def list_motif_patterns():
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
    except DotPlotError as e:
        raise HTTPException(status_code=400, detail=str(e))


class AlignmentInsightsRequest(BaseModel):
    aligned_sequences: list[str] = Field(..., min_length=2, description="Already aligned sequences of equal length; gaps use '-' or '.'")
    reference_index: int = Field(0, ge=0)
    variants: list[dict[str, Any]] = Field(default_factory=list, description="Optional variants with a 1-based ungapped reference 'position'")


@router.post("/alignment-insights")
async def analyze_alignment_insights(req: AlignmentInsightsRequest):
    """Return per-column conservation, Shannon entropy, sequence-logo weights and variant mapping."""
    try:
        return alignment_insights(req.aligned_sequences, req.reference_index, req.variants)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
