"""Sequence-tool endpoints: sequence utilities, motif scanner and dot plot.

All three are pure-local computations (no external services), so errors are
user-input errors and map to HTTP 400.
"""

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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/seq-tools", tags=["sequence-tools"])


# --- Sequence utilities ----------------------------------------------------


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


# --- Motif scanner ---------------------------------------------------------


class PatternScanRequest(BaseModel):
    sequence: str = Field(..., min_length=1, description="Protein sequence (raw or FASTA)")
    pattern: str = Field(..., min_length=1, description="PROSITE pattern, e.g. [ST]-x-[RK]")


class LibraryScanRequest(BaseModel):
    sequence: str = Field(..., min_length=1, description="Protein sequence (raw or FASTA)")
    categories: list[str] | None = Field(
        None, description="Optional category filter, e.g. ['PTM', 'DNA binding']"
    )


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
    """Return the curated motif library so the UI can offer presets."""
    return get_motif_patterns()


@router.get("/motif-library/categories")
async def list_motif_categories_endpoint():
    """Return the ordered list of motif categories for UI filters."""
    return list_motif_categories()


# --- Dot plot --------------------------------------------------------------


class DotPlotRequest(BaseModel):
    seq_a: str = Field(..., min_length=1, description="First sequence (query, vertical axis)")
    seq_b: str = Field(..., min_length=1, description="Second sequence (subject, horizontal axis)")
    window: int = Field(10, ge=1, le=200, description="Comparison window length")
    stringency: int = Field(80, ge=1, le=100, description="Percent identity/score required in the window")
    scoring: str = Field(
        "identity",
        description="Similarity scheme: identity (nucleotides) or a BLOSUM/PAM matrix (proteins)",
    )


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
        return compute_dotplot(
            req.seq_a,
            req.seq_b,
            window=req.window,
            stringency=req.stringency,
            scoring=req.scoring,
        )
    except DotPlotError as e:
        raise HTTPException(status_code=400, detail=str(e))
