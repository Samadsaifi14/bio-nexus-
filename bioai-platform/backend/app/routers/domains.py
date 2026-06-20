import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/domains", tags=["domains"])

INTERPRO_URL = "https://www.ebi.ac.uk/interpro/api/entry/all/protein/UniProt/{accession}/?format=json&page_size=50"

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

@router.get("/{accession}", response_model=DomainsResponse)
async def get_domains(accession: str):
    url = INTERPRO_URL.format(accession=accession.upper())
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        if r.status_code == 404:
            raise HTTPException(404, f"No InterPro data for {accession}")
        if r.status_code != 200:
            raise HTTPException(502, f"InterPro returned {r.status_code}")
        data = r.json()

    domains: list[Domain] = []
    seq_len = 0

    for result in data.get("results", []):
        entry = result.get("metadata", {})
        db    = entry.get("source_database", "").upper()
        acc   = entry.get("accession", "")
        name_raw = entry.get("name")
        if isinstance(name_raw, str):
            name_str = name_raw
        elif isinstance(name_raw, dict):
            name_str = name_raw.get("name", acc)
        else:
            name_str = acc

        for protein in result.get("proteins", []):
            if protein.get("accession", "").upper() != accession.upper():
                continue
            seq_len = protein.get("protein_length", seq_len)
            for loc in protein.get("entry_protein_locations", []):
                for fragment in loc.get("fragments", []):
                    domains.append(Domain(
                        accession=acc,
                        name=name_str,
                        source_db=db,
                        start=fragment.get("start", 0),
                        end=fragment.get("end", 0),
                        score=loc.get("score"),
                    ))

    domains.sort(key=lambda d: d.start)
    return DomainsResponse(
        uniprot_accession=accession.upper(),
        sequence_length=seq_len,
        domains=domains,
    )
