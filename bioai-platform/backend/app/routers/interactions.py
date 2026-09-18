import re
import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/interactions", tags=["interactions"])

STRING_NET = "https://string-db.org/api/json/interaction_partners"

# Network types supported by STRING-DB
# "functional" = all evidence channels (default, same as combined)
# "physical"   = only direct physical binding (experimental + database)
NETWORK_TYPES = {"functional", "physical"}


def _sanitize_for_url(s: str) -> str:
    """Strip control characters that break URL construction."""
    return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)


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
    # LOCAL heuristic, NOT a STRING-provided score: simple mean of the
    # experimental + database evidence channels. Never label it as STRING's
    # "physical" confidence.
    physical_evidence_avg: float | None = None


@router.get("/{gene_name}")
async def get_interactions(
    gene_name: str,
    species: int = Query(default=9606, description="NCBI taxon ID; 9606=human"),
    limit: int = Query(default=15, ge=1, le=50),
    network_type: str = Query(
        default="functional",
        description="'functional' (all evidence) or 'physical' (direct binding only)",
    ),
):
    gene_name = _sanitize_for_url(gene_name)
    network_type = network_type.lower()
    if network_type not in NETWORK_TYPES:
        raise HTTPException(400, f"Invalid network_type '{network_type}'. Use 'functional' or 'physical'.")

    params = {
        "identifiers": gene_name,
        "species": species,
        "limit": limit,
        "caller_identity": "bio-nexus-platform",
    }
    # STRING API supports network_type parameter
    if network_type == "physical":
        params["network_type"] = "physical"

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(STRING_NET, params=params)
        if r.status_code != 200:
            raise HTTPException(502, f"STRING-DB returned {r.status_code}")
        data = r.json()

    if not data:
        raise HTTPException(404, f"No interactions found for {gene_name}")

    interactions = []
    for item in data:
        # STRING scores are 0-1000; normalize to 0-1 so thresholds and
        # consumers treat them consistently across channels.
        def norm(v):
            try:
                return min(1.0, max(0.0, float(v) / 1000.0))
            except (TypeError, ValueError):
                return 0.0

        nscore = norm(item.get("nscore"))
        fscore = norm(item.get("fscore"))
        pscore = norm(item.get("pscore"))
        ascore = norm(item.get("ascore"))
        escore = norm(item.get("escore"))
        dscore = norm(item.get("dscore"))
        tscore = norm(item.get("tscore"))
        combined = norm(item.get("score"))

        # Local heuristic: mean of the experimental + database evidence
        # channels. Derived by Bio Nexus for display; not a STRING-provided
        # score and not a substitute for STRING's combined confidence.
        physical_evidence_avg = round((escore + dscore) / 2, 4) if (escore or dscore) else None

        interactions.append(Interaction(
            partner_gene=item.get("preferredName_B", ""),
            partner_protein=item.get("stringId_B", ""),
            combined_score=combined,
            nscore=nscore,
            fscore=fscore,
            pscore=pscore,
            ascore=ascore,
            escore=escore,
            dscore=dscore,
            tscore=tscore,
            physical_evidence_avg=physical_evidence_avg,
        ))

    interactions.sort(key=lambda x: x.combined_score, reverse=True)
    result = {
        "gene": gene_name,
        "species": species,
        "network_type": network_type,
        "source": "STRING-DB interaction_partners API",
        "score_scale": "0-1 (normalized from STRING's 0-1000 confidence)",
        "score_derivations": [
            "combined_score is STRING's combined confidence value, normalized from its native 0-1000 scale.",
            "nscore/fscore/pscore/ascore/escore/dscore/tscore are STRING's per-channel evidence scores, normalized from 0-1000.",
            "physical_evidence_avg is a LOCAL Bio Nexus heuristic (mean of experimental + database channels), not a STRING-provided score.",
        ],
        "interactions": interactions,
    }

    # AI interpretation (best-effort, never blocks)
    try:
        from app.ai.tool_interpreter import interpret_tool_result
        ai_interp = await interpret_tool_result("interactions", result)
        if ai_interp:
            result["ai_interpretation"] = ai_interp
    except Exception:
        pass

    return result
