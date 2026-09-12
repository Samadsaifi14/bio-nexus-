import secrets

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.services.auth import require_user_id
from app.services.supabase import get_supabase

router = APIRouter()


class ShareRequest(BaseModel):
    job_id: str


@router.get("/{token}")
async def get_shared_result(token: str):
    """Return a result only through an explicit high-entropy share token."""
    supabase = get_supabase()
    result = supabase.table("jobs").select("*").eq("share_token", token).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Shared result not found")
    job = result.data[0]

    # Hydrate the full context from Storage only after the explicit token matched.
    if job.get("storage_url") and not (job.get("context_json") or {}).get("blast"):
        from app.services.artifact_storage import download_json
        results = download_json(job["storage_url"])
        if results:
            job["context_json"] = results
            job["results"] = results

    return job


@router.post("")
async def create_share_link(req: ShareRequest, user_id: str = Depends(require_user_id)):
    """Create/reuse a public share token for a job owned by the caller.

    The service-role database client bypasses RLS, therefore ownership is part of
    the database predicate rather than a post-fetch comparison. Legacy anonymous
    jobs are intentionally not shareable through this endpoint.
    """
    supabase = get_supabase()
    result = (
        supabase.table("jobs")
        .select("id,user_id,share_token")
        .eq("id", req.job_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Job not found")

    existing = result.data[0].get("share_token")
    if existing:
        token = existing
    else:
        token = secrets.token_urlsafe(32)
        (
            supabase.table("jobs")
            .update({"share_token": token})
            .eq("id", req.job_id)
            .eq("user_id", user_id)
            .execute()
        )
    return {"token": token, "url": f"/shared/{token}"}
