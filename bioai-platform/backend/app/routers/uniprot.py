from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.tools.uniprot import UniprotTool
from app.services.ncbi_service import NCBIService
import httpx
from app.config import settings

router = APIRouter()
uniprot_tool = UniprotTool()
ncbi_service = NCBIService()


class UniprotSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Free-text search (gene name, protein name, keyword)")
    max_results: int = Field(20, ge=1, le=50)
    reviewed: bool = Field(False, description="Only Swiss-Prot (reviewed) entries")
    organism: str = Field("", description="Restrict results to an organism (e.g. Homo sapiens)")


class UniprotAccessionRequest(BaseModel):
    accession: str = Field(..., min_length=1, description="UniProt accession (e.g. P04637)")


class UniprotCDSRequest(BaseModel):
    accession: str = Field(..., min_length=1, description="UniProt accession")
    embl_accession: str = Field(..., min_length=1, description="EMBL/GenBank nucleotide accession")


def _versionless_accession(value: str) -> str:
    """Return an uppercase accession without an optional final `.version` suffix."""
    token = (value or "").strip().upper()
    head, dot, tail = token.rpartition(".")
    if dot and head and tail.isdigit():
        return head
    return token


def _matching_cds_crossref(detail: dict, requested: str) -> dict | None:
    requested_full = (requested or "").strip().upper()
    requested_base = _versionless_accession(requested_full)
    for ref in detail.get("cds_accessions") or []:
        accession = str((ref or {}).get("accession") or "").strip().upper()
        if not accession:
            continue
        if requested_full == accession or requested_base == _versionless_accession(accession):
            return ref
    return None


@router.post("/search")
async def search_uniprot(req: UniprotSearchRequest):
    url = f"{settings.UNIPROT_BASE_URL}/search"
    query = req.query.strip()
    if req.organism.strip():
        query = f'{query} AND organism_name:"{req.organism.strip()}"'
    if req.reviewed:
        query = f"{query} AND reviewed:true"
    params = {"query": query, "format": "json", "size": req.max_results}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"UniProt search request failed: {exc.__class__.__name__}")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="UniProt search failed")
    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="UniProt search returned malformed JSON")
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="UniProt search returned an unexpected payload")

    results = data.get("results") or []
    if not isinstance(results, list):
        raise HTTPException(status_code=502, detail="UniProt search results were malformed")

    out = []
    for r in results:
        if not isinstance(r, dict):
            continue
        out.append({
            "accession": r.get("primaryAccession", ""),
            "name": uniprot_tool._extract_name(r),
            "gene_names": [
                g.get("geneName", {}).get("value", "")
                for g in (r.get("genes") or [])
                if isinstance(g, dict) and g.get("geneName") and g.get("geneName", {}).get("value")
            ],
            "organism": (r.get("organism", {}) or {}).get("scientificName", ""),
            "length": ((r.get("sequence", {}) or {}).get("length", 0)),
            "reviewed": uniprot_tool._is_reviewed(r),
        })
    return {"results": out, "count": len(out)}


@router.post("/detail")
async def uniprot_detail(req: UniprotAccessionRequest):
    result = await uniprot_tool.run({"accession": req.accession})
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/cds")
async def fetch_uniprot_cds(req: UniprotCDSRequest):
    """Fetch a nucleotide record only after verifying its UniProt cross-reference.

    The old endpoint accepted any arbitrary EMBL/GenBank accession next to any
    UniProt accession. That could create a scientifically false protein-to-CDS
    relationship. The relationship is now established from the current
    UniProtKB entry before NCBI retrieval is attempted.
    """
    detail = await uniprot_tool.run({"accession": req.accession})
    if "error" in detail:
        raise HTTPException(status_code=404, detail=detail["error"])

    crossref = _matching_cds_crossref(detail, req.embl_accession)
    if crossref is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{req.embl_accession!r} is not documented as an EMBL/GenBank/DDBJ "
                f"cross-reference for UniProt entry {detail.get('accession') or req.accession}. "
                "No CDS relationship was inferred."
            ),
        )

    result = await ncbi_service.fetch_by_accession(req.embl_accession.strip())
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {
        "uniprot_accession": detail.get("accession") or req.accession.strip().upper(),
        "embl_accession": req.embl_accession.strip().upper(),
        "sequence": result.get("sequence", ""),
        "length": result.get("length", 0),
        "description": result.get("description", ""),
        "organism": result.get("organism", ""),
        "cross_reference_verified": True,
        "cross_reference": crossref,
        "uniprot_source": detail.get("source", "UniProtKB"),
        "uniprot_entry_version": detail.get("entry_version"),
    }
