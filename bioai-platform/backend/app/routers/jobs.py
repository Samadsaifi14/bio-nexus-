from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone

from app.services.supabase import get_supabase
from app.services.auth import require_user_id
from app.models.responses import JobCountResponse, JobDeleteResponse

router = APIRouter()


def _owned_job_or_404(job_id: str, user_id: str, *, fields: str = "*, parent_job_id") -> dict:
    """Fetch one job through the service-role client while preserving tenant isolation.

    The backend Supabase client uses a service-role credential and therefore bypasses
    database RLS. Every user-facing query must include the authenticated owner in the
    database predicate itself; checking ownership only after an unrestricted read risks
    exposing private sequence/context data and creates an IDOR surface.
    """
    supabase = get_supabase()
    result = (
        supabase.table("jobs")
        .select(fields)
        .eq("id", job_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        # Do not reveal whether the UUID belongs to another account.
        raise HTTPException(status_code=404, detail="Job not found")
    return result.data[0]


@router.get("/count", response_model=JobCountResponse)
async def job_count(user_id: str = Depends(require_user_id)):
    supabase = get_supabase()
    today = datetime.now(timezone.utc).date().isoformat()
    result = (
        supabase.table("jobs")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .gte("created_at", today)
        .execute()
    )
    count = result.count or 0
    return {"count": count, "limit": 10, "remaining": max(0, 10 - count)}


@router.get("")
async def list_jobs(user_id: str = Depends(require_user_id)):
    try:
        supabase = get_supabase()
        result = (
            supabase.table("jobs")
            .select("*, parent_job_id")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return {"jobs": result.data or []}
    except HTTPException:
        raise
    except Exception as exc:
        # Do not echo provider details, SQL, table names or credentials to the client.
        raise HTTPException(status_code=500, detail="Could not list jobs") from exc


@router.get("/{job_id}")
async def get_job(job_id: str, user_id: str = Depends(require_user_id)):
    job = _owned_job_or_404(job_id, user_id)

    # Hydrate from Storage if result was offloaded. Ownership has already been
    # established above; an unowned job never reaches artifact retrieval.
    if job.get("storage_url") and not job.get("context_json", {}).get("blast"):
        from app.services.artifact_storage import download_json
        results = download_json(job["storage_url"])
        if results:
            job["context_json"] = results
            job["results"] = results

    return job


@router.delete("/{job_id}", response_model=JobDeleteResponse)
async def delete_job(job_id: str, user_id: str = Depends(require_user_id)):
    _owned_job_or_404(job_id, user_id, fields="id,user_id")
    supabase = get_supabase()
    supabase.table("jobs").delete().eq("id", job_id).eq("user_id", user_id).execute()
    return {"status": "deleted"}
