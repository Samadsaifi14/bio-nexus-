"""
Domain & Motif Analysis endpoints.

Provides comprehensive protein feature analysis:
  - InterPro domain architecture (Pfam, SMART, PROSITE, CDD, PANTHER, PRINTS)
  - Functional sites (active, binding, catalytic residues)
  - Post-translational modifications (phosphorylation, glycosylation, etc.)
  - Topology (signal peptides, transmembrane regions, chains)
  - Structural motifs (zinc fingers, coiled coils, domains)
  - Mutagenesis & natural variants
  - Disulfide bonds
  - Composition bias (low complexity, repeats)
  - Gene Ontology annotations
  - Pathway annotations (KEGG, Reactome, WikiPathways)
  - Combined analysis endpoint
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.tools.domain_analysis import (
    _sanitize,
    fetch_interpro_domains,
    fetch_uniprot_raw,
    extract_features,
    extract_functional_sites,
    extract_ptms,
    extract_topology,
    extract_structural_motifs,
    extract_variants,
    extract_disulfide_bonds,
    extract_composition_bias,
    extract_go_terms,
    extract_pathways,
    full_analysis,
)

router = APIRouter(prefix="/api/domains", tags=["domains"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class Domain(BaseModel):
    accession: str
    name: str
    source_db: str
    start: int
    end: int
    score: float | None


class DomainsResponse(BaseModel):
    uniprot_accession: str
    sequence_length: int
    domains: list[Domain]


class FeatureItem(BaseModel):
    type: str
    description: str
    begin: int | None = None
    end: int | None = None
    amino_acid: list[str] = []


class FeaturesResponse(BaseModel):
    accession: str
    sequence_length: int
    categories: dict[str, list[FeatureItem]]


class FunctionalSite(BaseModel):
    type: str
    description: str
    begin: int | None = None
    end: int | None = None
    amino_acid: list[str] = []


class PTMItem(BaseModel):
    type: str
    description: str
    begin: int | None = None
    end: int | None = None
    amino_acid: list[str] = []


class TopologyItem(BaseModel):
    type: str
    description: str
    begin: int | None = None
    end: int | None = None


class MotifItem(BaseModel):
    type: str
    description: str
    begin: int | None = None
    end: int | None = None


class VariantItem(BaseModel):
    type: str
    description: str
    begin: int | None = None
    end: int | None = None
    amino_acid: list[str] = []


class DisulfideBond(BaseModel):
    begin: int | None = None
    end: int | None = None
    description: str = ""


class CompositionBias(BaseModel):
    type: str
    description: str
    begin: int | None = None
    end: int | None = None


class GOTerm(BaseModel):
    id: str
    term: str
    category: str


class PathwayAnnotation(BaseModel):
    database: str
    id: str
    name: str


class FullAnalysisResponse(BaseModel):
    accession: str
    protein_name: str
    organism: str
    sequence_length: int
    sequence: str
    domains: list[Domain]
    active_sites: list[FunctionalSite]
    ptms: list[PTMItem]
    topology: list[TopologyItem]
    structural_motifs: list[MotifItem]
    variants: list[VariantItem]
    disulfide_bonds: list[DisulfideBond]
    composition_bias: list[CompositionBias]
    go_terms: list[GOTerm]
    pathways: list[PathwayAnnotation]
    feature_summary: dict[str, int]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{accession}", response_model=DomainsResponse)
async def get_domains(accession: str):
    """Fetch InterPro domain architecture (Pfam, SMART, PROSITE, CDD, PANTHER, PRINTS)."""
    accession = _sanitize(accession)
    try:
        data = await fetch_interpro_domains(accession)
    except Exception as e:
        raise HTTPException(502, f"InterPro request failed: {e}")
    if not data.get("domains"):
        raise HTTPException(404, f"No domain annotations found for {accession}")
    return DomainsResponse(**data)


@router.get("/{accession}/features", response_model=FeaturesResponse)
async def get_features(accession: str):
    """Full UniProt feature table categorized by type."""
    accession = _sanitize(accession)
    raw = await _fetch_or_404(accession)
    features = extract_features(raw)
    seq_len = (raw.get("sequence", {}) or {}).get("length", 0)
    categories = {
        cat: [FeatureItem(**item) for item in items]
        for cat, items in features.items() if items
    }
    return FeaturesResponse(
        accession=accession, sequence_length=seq_len, categories=categories,
    )


@router.get("/{accession}/sites", response_model=list[FunctionalSite])
async def get_functional_sites(accession: str):
    """Active sites, binding sites, and catalytic residues."""
    accession = _sanitize(accession)
    raw = await _fetch_or_404(accession)
    sites = extract_functional_sites(raw)
    return [FunctionalSite(**s) for s in sites]


@router.get("/{accession}/ptm", response_model=list[PTMItem])
async def get_ptms(accession: str):
    """Post-translational modifications (phosphorylation, glycosylation, etc.)."""
    accession = _sanitize(accession)
    raw = await _fetch_or_404(accession)
    ptms = extract_ptms(raw)
    return [PTMItem(**p) for p in ptms]


@router.get("/{accession}/topology", response_model=list[TopologyItem])
async def get_topology(accession: str):
    """Signal peptides, transmembrane regions, chains, and propeptides."""
    accession = _sanitize(accession)
    raw = await _fetch_or_404(accession)
    topo = extract_topology(raw)
    return [TopologyItem(**t) for t in topo]


@router.get("/{accession}/motifs", response_model=list[MotifItem])
async def get_motifs(accession: str):
    """Structural motifs: zinc fingers, coiled coils, repeats, domain families."""
    accession = _sanitize(accession)
    raw = await _fetch_or_404(accession)
    motifs = extract_structural_motifs(raw)
    return [MotifItem(**m) for m in motifs]


@router.get("/{accession}/variants", response_model=list[VariantItem])
async def get_variants(accession: str):
    """Mutagenesis sites and natural variants."""
    accession = _sanitize(accession)
    raw = await _fetch_or_404(accession)
    variants = extract_variants(raw)
    return [VariantItem(**v) for v in variants]


@router.get("/{accession}/disulfide", response_model=list[DisulfideBond])
async def get_disulfide_bonds(accession: str):
    """Disulfide bond connectivity."""
    accession = _sanitize(accession)
    raw = await _fetch_or_404(accession)
    bonds = extract_disulfide_bonds(raw)
    return [DisulfideBond(**b) for b in bonds]


@router.get("/{accession}/composition", response_model=list[CompositionBias])
async def get_composition_bias(accession: str):
    """Compositionally biased regions and low-complexity sequences."""
    accession = _sanitize(accession)
    raw = await _fetch_or_404(accession)
    bias = extract_composition_bias(raw)
    return [CompositionBias(**b) for b in bias]


@router.get("/{accession}/go", response_model=list[GOTerm])
async def get_go_terms(accession: str):
    """Gene Ontology annotations (molecular function, biological process, cellular component)."""
    accession = _sanitize(accession)
    raw = await _fetch_or_404(accession)
    go = extract_go_terms(raw)
    return [GOTerm(**g) for g in go]


@router.get("/{accession}/pathways", response_model=list[PathwayAnnotation])
async def get_pathways(accession: str):
    """Pathway annotations from KEGG, Reactome, and WikiPathways."""
    accession = _sanitize(accession)
    raw = await _fetch_or_404(accession)
    pws = extract_pathways(raw)
    return [PathwayAnnotation(**p) for p in pws]


@router.get("/{accession}/all", response_model=FullAnalysisResponse)
async def get_all_features(accession: str):
    """Combined analysis: domains, sites, PTMs, topology, motifs, variants, GO, pathways."""
    accession = _sanitize(accession)
    try:
        result = await full_analysis(accession)
    except Exception as e:
        raise HTTPException(502, f"Analysis failed: {e}")
    if not result.get("domains") and not result.get("active_sites"):
        raise HTTPException(404, f"No feature data found for {accession}")
    return FullAnalysisResponse(**result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _fetch_or_404(accession: str) -> dict:
    raw = await fetch_uniprot_raw(accession)
    if not raw:
        raise HTTPException(404, f"No UniProt data for {accession}")
    return raw
