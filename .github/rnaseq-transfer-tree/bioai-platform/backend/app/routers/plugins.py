"""Read-only plugin inventory.

Plugin discovery/enabling/event dispatch alter global server behavior and therefore belong to
deployment administration, not the public application API. The HTTP surface only exposes a
sanitized inventory to authenticated users.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import require_user_id
from app.services.plugin_system import plugin_manager

router = APIRouter(tags=["plugins"])


@router.get("/api/plugins")
async def plugins_list(user_id: str = Depends(require_user_id)):
    return {"plugins": plugin_manager.list_plugins()}


@router.post("/api/plugins/reload")
async def plugins_reload(user_id: str = Depends(require_user_id)):
    raise HTTPException(status_code=403, detail="Plugin reload is deployment-admin controlled")


@router.post("/api/plugins/{name}/enable")
async def plugins_enable(name: str, user_id: str = Depends(require_user_id)):
    raise HTTPException(status_code=403, detail="Plugin enablement is deployment-admin controlled")


@router.post("/api/plugins/{name}/disable")
async def plugins_disable(name: str, user_id: str = Depends(require_user_id)):
    raise HTTPException(status_code=403, detail="Plugin enablement is deployment-admin controlled")


class PluginEventRequest(BaseModel):
    event: str
    payload: dict = {}


@router.post("/api/plugins/event")
async def plugins_event(body: PluginEventRequest, user_id: str = Depends(require_user_id)):
    raise HTTPException(status_code=403, detail="Plugin event dispatch is not exposed through the public API")
