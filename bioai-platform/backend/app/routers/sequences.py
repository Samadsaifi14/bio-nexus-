from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.services.ncbi_service import NCBIService
from app.services.sequence_utils import validate_sequence, detect_source_from_accession
from app.tools.uniprot import UniprotTool

router = APIRouter()
ncbi_service = NCBIService()
uniprot_tool = UniprotTool()


class FetchRequest(BaseModel):
    accession: str = Field(..., min_length=1, description="Accession number (e.g. NP_000509.1, P12345, 1TIM)")
    db_preference: Optional[str] = Field(None, description="Preferred database: 'ncbi', 'uniprot', or 'pdb'")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Gene or protein name to search")
    db: str = Field("protein", description="NCBI database to search")
    max_results: int = Field(10, ge=1, le=50)


class ValidateRequest(BaseModel):
    sequence: str = Field(..., min_length=1, description="Raw sequence string or FASTA")


@router.post("/fetch")
async def fetch_sequence(req: FetchRequest):
    accession = req.accession.strip()
    db_pref = req.db_preference or detect_source_from_accession(accession)
    if db_pref == "uniprot":
        result = await uniprot_tool.run({"accession": accession})
        if "error" not in result:
            seq = result.get("sequence", "")
            from app.services.sequence_utils import detect_sequence_type
            return {
                "accession": result["accession"],
                "db_source": "uniprot",
                "sequence_type": detect_sequence_type(seq) if seq else "protein",
                "sequence": seq,
                "length": result.get("sequence_length", 0),
                "organism": result.get("organism", ""),
                "description": result.get("full_name", ""),
                "gene_names": result.get("gene_names", []),
                "functions": result.get("functions", []),
                "keywords": result.get("keywords", []),
                "go_terms": result.get("go_terms", []),
                "features": result.get("features", []),
                "pdb_ids": result.get("pdb_ids", []),
                "from_cache": False,
            }
        if db_pref == "uniprot" and "error" in result:
            pass
    result = await ncbi_service.fetch_by_accession(accession)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/validate")
async def validate_sequence_endpoint(req: ValidateRequest):
    return validate_sequence(req.sequence)


@router.post("/search")
async def search_sequences(req: SearchRequest):
    result = await ncbi_service.search_by_name(req.query, db=req.db, max_results=req.max_results)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
