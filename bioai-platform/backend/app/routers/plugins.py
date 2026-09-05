"""Plugin System routes (Component 20).

- GET  /api/plugins                — discovered plugins + enabled state.
- POST /api/plugins/reload         — re-discover the plugin directory.
- POST /api/plugins/{name}/enable  — activate a plugin.
- POST /api/plugins/{name}/disable — deactivate a plugin.
- POST /api/plugins/event          — dispatch a platform event to plugins.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import get_user_id
from app.services.plugin_system import plugin_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["plugins"])


@router.get("/api/plugins")
async def plugins_list(user_id: str | None = Depends(get_user_id)):
    return {"plugins": plugin_manager.list_plugins(),
            "plugin_dir": plugin_manager.dir,
            "trace_entries": len(plugin_manager.trace)}


@router.post("/api/plugins/reload")
async def plugins_reload(user_id: str | None = Depends(get_user_id)):
    loaded = plugin_manager.reload()
    return {"reloaded": loaded, "plugins": plugin_manager.list_plugins()}


@router.post("/api/plugins/{name}/enable")
async def plugins_enable(name: str, user_id: str | None = Depends(get_user_id)):
    if not plugin_manager.set_enabled(name, True):
        raise HTTPException(status_code=404, detail=f"unknown plugin '{name}'")
    return {"name": name, "enabled": True}


@router.post("/api/plugins/{name}/disable")
async def plugins_disable(name: str, user_id: str | None = Depends(get_user_id)):
    if not plugin_manager.set_enabled(name, False):
        raise HTTPException(status_code=404, detail=f"unknown plugin '{name}'")
    return {"name": name, "enabled": False}


class PluginEventRequest(BaseModel):
    event: str
    payload: dict = {}


@router.post("/api/plugins/event")
async def plugins_event(body: PluginEventRequest, user_id: str | None = Depends(get_user_id)):
    return {"event": body.event, "records": plugin_manager.run_event(body.event, body.payload)}