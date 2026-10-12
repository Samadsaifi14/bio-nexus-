"""Private pipeline templates with explicit token-based sharing."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.auth import require_user_id
from app.services.supabase import get_supabase

router = APIRouter()
STEP_ORDER = ["blast", "uniprot", "msa", "phylo", "domains", "pathway_enrichment", "alphafold", "interpret"]


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    steps: list[str]
    parameters: dict = {}


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    steps: list[str] | None = None
    parameters: dict | None = None


def _owned_template(template_id: str, user_id: str, fields: str = "*") -> dict:
    result = (
        get_supabase().table("pipeline_templates")
        .select(fields)
        .eq("id", template_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Template not found")
    return result.data[0]


@router.get("")
async def list_templates(user_id: str = Depends(require_user_id)):
    result = (
        get_supabase().table("pipeline_templates")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"templates": result.data or []}


@router.post("")
async def create_template(req: TemplateCreate, user_id: str = Depends(require_user_id)):
    invalid = [step for step in req.steps if step not in STEP_ORDER]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown steps: {invalid}")
    payload = {
        "name": req.name.strip(),
        "description": req.description,
        "steps": req.steps,
        "parameters": req.parameters,
        "user_id": user_id,
    }
    result = get_supabase().table("pipeline_templates").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create template")
    return result.data[0]


@router.get("/shared/{token}")
async def get_shared_template(token: str):
    result = (
        get_supabase().table("pipeline_templates")
        .select("*")
        .eq("share_token", token)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Shared template not found")
    return result.data[0]


@router.get("/{template_id}")
async def get_template(template_id: str, user_id: str = Depends(require_user_id)):
    return _owned_template(template_id, user_id)


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    req: TemplateUpdate,
    user_id: str = Depends(require_user_id),
):
    current = _owned_template(template_id, user_id)
    updates = {}
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=422, detail="Name is required")
        updates["name"] = req.name.strip()
    if req.description is not None:
        updates["description"] = req.description
    if req.steps is not None:
        invalid = [step for step in req.steps if step not in STEP_ORDER]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Unknown steps: {invalid}")
        updates["steps"] = req.steps
    if req.parameters is not None:
        updates["parameters"] = req.parameters
    if not updates:
        return current
    (
        get_supabase().table("pipeline_templates")
        .update(updates)
        .eq("id", template_id)
        .eq("user_id", user_id)
        .execute()
    )
    return {**current, **updates}


@router.delete("/{template_id}")
async def delete_template(template_id: str, user_id: str = Depends(require_user_id)):
    _owned_template(template_id, user_id, "id")
    (
        get_supabase().table("pipeline_templates")
        .delete()
        .eq("id", template_id)
        .eq("user_id", user_id)
        .execute()
    )
    return {"status": "deleted"}


@router.post("/{template_id}/share")
async def share_template(template_id: str, user_id: str = Depends(require_user_id)):
    template = _owned_template(template_id, user_id)
    if template.get("share_token"):
        token = template["share_token"]
    else:
        token = secrets.token_urlsafe(32)
        (
            get_supabase().table("pipeline_templates")
            .update({"share_token": token})
            .eq("id", template_id)
            .eq("user_id", user_id)
            .execute()
        )
    return {"token": token, "url": f"/templates/shared/{token}"}
