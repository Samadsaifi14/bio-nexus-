"""Research Dataset Library routes."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import get_user_id
from app.services.dataset_library import dataset_lineage, get_dataset, list_datasets, snapshot_dataset, validate_dataset

logger=logging.getLogger(__name__); router=APIRouter(tags=["datasets"])

@router.get("/api/datasets")
async def datasets_list(user_id:str|None=Depends(get_user_id)):
    datasets=list_datasets(); return {"datasets":datasets,"count":len(datasets)}

@router.get("/api/datasets/{name}")
async def datasets_get(name:str,user_id:str|None=Depends(get_user_id)):
    dataset=get_dataset(name)
    if dataset is None:raise HTTPException(status_code=404,detail=f"Unknown dataset '{name}'")
    return dataset

@router.get("/api/datasets/{name}/validate")
async def datasets_validate(name:str,user_id:str|None=Depends(get_user_id)):
    result=validate_dataset(name)
    if result.get("checks") and not result["checks"][0].get("passed"):raise HTTPException(status_code=404,detail=f"Unknown dataset '{name}'")
    return result

@router.get("/api/datasets/{name}/lineage")
async def datasets_lineage(name:str,user_id:str|None=Depends(get_user_id)):
    result=dataset_lineage(name)
    if result.get("error"):raise HTTPException(status_code=404,detail=f"Unknown dataset '{name}'")
    return result

class SnapshotRequest(BaseModel): target_dir:str

@router.post("/api/datasets/{name}/snapshot")
async def datasets_snapshot(name:str,body:SnapshotRequest,user_id:str|None=Depends(get_user_id)):
    if not body.target_dir.strip():raise HTTPException(status_code=422,detail="target_dir is required")
    try:return snapshot_dataset(name,body.target_dir)
    except ValueError as exc:raise HTTPException(status_code=404,detail=str(exc))
    except OSError as exc:raise HTTPException(status_code=400,detail=f"target_dir not usable: {exc}")
