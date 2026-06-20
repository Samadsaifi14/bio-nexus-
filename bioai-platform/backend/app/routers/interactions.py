import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/interactions", tags=["interactions"])

STRING_NET = "https://string-db.org/api/json/interaction_partners"

class Interaction(BaseModel):
    partner_gene: str
    partner_protein: str
    combined_score: float
    nscore: float
    fscore: float
    pscore: float
    ascore: float
    escore: float
    dscore: float
    tscore: float

@router.get("/{gene_name}")
async def get_interactions(
    gene_name: str,
    species: int = Query(default=9606, description="NCBI taxon ID; 9606=human"),
    limit: int = Query(default=15, ge=1, le=50),
):
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(STRING_NET, params={
            "identifiers": gene_name,
            "species":     species,
            "limit":       limit,
            "caller_identity": "bio-nexus-platform",
        })
        if r.status_code != 200:
            raise HTTPException(502, f"STRING-DB returned {r.status_code}")
        data = r.json()

    if not data:
        raise HTTPException(404, f"No interactions found for {gene_name}")

    interactions = [
        Interaction(
            partner_gene    = item.get("preferredName_B", ""),
            partner_protein = item.get("stringId_B", ""),
            combined_score  = item.get("score", 0) / 1000,
            nscore          = item.get("nscore", 0) / 1000,
            fscore          = item.get("fscore", 0) / 1000,
            pscore          = item.get("pscore", 0) / 1000,
            ascore          = item.get("ascore", 0) / 1000,
            escore          = item.get("escore", 0) / 1000,
            dscore          = item.get("dscore", 0) / 1000,
            tscore          = item.get("tscore", 0) / 1000,
        )
        for item in data
    ]
    interactions.sort(key=lambda x: x.combined_score, reverse=True)
    return {"gene": gene_name, "species": species, "interactions": interactions}
