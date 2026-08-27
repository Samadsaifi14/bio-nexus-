"""Pipeline templates — save, load, share named pipeline configurations."""

import secrets

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.auth import get_user_id
from app.services.supabase import get_supabase

router = APIRouter()

STEP_ORDER = ["blast", "uniprot", "msa", "phylo", "domains", "pathway_enrichment", "alphafold", "interpret"]


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    steps: list[str]
    parameters: dict = {}


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    steps: list[str] | None = None
    parameters: dict | None = None


@router.get("")
async def list_templates(user_id: str | None = Depends(get_user_id)):
    supabase = get_supabase()
    query = supabase.table("pipeline_templates").select("*").order("created_at", desc=True)
    if user_id:
        query = query.eq("user_id", user_id)
    result = query.execute()
    return {"templates": result.data or []}


@router.post("")
async def create_template(req: TemplateCreate, user_id: str | None = Depends(get_user_id)):
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    invalid = [s for s in req.steps if s not in STEP_ORDER]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown steps: {invalid}")
    supabase = get_supabase()
    payload = {
        "name": req.name.strip(),
        "description": req.description,
        "steps": req.steps,
        "parameters": req.parameters,
        "user_id": user_id,
    }
    result = supabase.table("pipeline_templates").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create template")
    return result.data[0]


@router.get("/{template_id}")
async def get_template(template_id: str, user_id: str | None = Depends(get_user_id)):
    supabase = get_supabase()
    result = supabase.table("pipeline_templates").select("*").eq("id", template_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Template not found")
    t = result.data[0]
    if user_id and t.get("user_id") and t["user_id"] != user_id:
        # Allow public shared templates
        if not t.get("share_token"):
            raise HTTPException(status_code=403, detail="Access denied")
    return t


@router.get("/shared/{token}")
async def get_shared_template(token: str):
    supabase = get_supabase()
    result = supabase.table("pipeline_templates").select("*").eq("share_token", token).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Shared template not found")
    return result.data[0]


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    req: TemplateUpdate,
    user_id: str | None = Depends(get_user_id),
):
    supabase = get_supabase()
    existing = supabase.table("pipeline_templates").select("*").eq("id", template_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Template not found")
    t = existing.data[0]
    if user_id and t.get("user_id") and t["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    updates = {}
    if req.name is not None:
        updates["name"] = req.name.strip()
    if req.description is not None:
        updates["description"] = req.description
    if req.steps is not None:
        invalid = [s for s in req.steps if s not in STEP_ORDER]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Unknown steps: {invalid}")
        updates["steps"] = req.steps
    if req.parameters is not None:
        updates["parameters"] = req.parameters
    if not updates:
        return t
    supabase.table("pipeline_templates").update(updates).eq("id", template_id).execute()
    return {**t, **updates}


@router.delete("/{template_id}")
async def delete_template(template_id: str, user_id: str | None = Depends(get_user_id)):
    supabase = get_supabase()
    existing = supabase.table("pipeline_templates").select("id, user_id").eq("id", template_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Template not found")
    t = existing.data[0]
    if user_id and t.get("user_id") and t["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    supabase.table("pipeline_templates").delete().eq("id", template_id).execute()
    return {"status": "deleted"}


@router.post("/{template_id}/share")
async def share_template(template_id: str, user_id: str | None = Depends(get_user_id)):
    supabase = get_supabase()
    existing = supabase.table("pipeline_templates").select("*").eq("id", template_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Template not found")
    t = existing.data[0]
    if user_id and t.get("user_id") and t["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if t.get("share_token"):
        return {"token": t["share_token"], "url": f"/templates/shared/{t['share_token']}"}
    token = secrets.token_urlsafe(16)
    supabase.table("pipeline_templates").update({"share_token": token}).eq("id", template_id).execute()
    return {"token": token, "url": f"/templates/shared/{token}"}
