"""Versioned research dataset library with integrity and lineage manifests."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)
DATASETS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "datasets")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _index() -> dict:
    path=os.path.join(DATASETS_DIR,"index.json")
    try:
        with open(path,encoding="utf-8") as f:return json.load(f)
    except Exception as exc:
        logger.warning("Dataset index read failed: %s",exc); return {"datasets":[]}


def list_datasets() -> list[dict]:
    rows=[]
    for d in _index().get("datasets") or []:
        row={k:d.get(k) for k in ("name","category","type","date","version","records_count","description","citation","ground_truth","parent_version","source")}
        payload=get_dataset(str(d.get("name") or "")) if d.get("name") else None
        row["dataset_sha256"]=_sha(payload) if payload is not None else None
        rows.append(row)
    return rows


def get_dataset(name:str)->Optional[dict]:
    if not name or any(x in name for x in ("/","\\","..")): return None
    path=os.path.join(DATASETS_DIR,f"{name}.json")
    if not os.path.isfile(path):return None
    try:
        with open(path,encoding="utf-8") as f:return json.load(f)
    except Exception as exc:
        logger.warning("Dataset %s read failed: %s",name,exc); return None


def validate_dataset(name:str)->dict:
    dataset=get_dataset(name)
    if dataset is None:return {"dataset":name,"valid":False,"checks":[{"name":"exists","passed":False}]}
    records=dataset.get("records")
    checks=[
      {"name":"exists","passed":True},
      {"name":"version_recorded","passed":bool(dataset.get("version")),"detail":dataset.get("version")},
      {"name":"records_array","passed":isinstance(records,list),"detail":type(records).__name__},
      {"name":"citation_or_source","passed":bool(dataset.get("citation") or dataset.get("source")),"detail":"external provenance present" if dataset.get("citation") or dataset.get("source") else "missing"},
      {"name":"ground_truth_label_explicit","passed":"ground_truth" in dataset or str(dataset.get("category","")).lower() not in {"ground-truth","ground_truth","truth"},"detail":dataset.get("ground_truth")},
    ]
    return {"dataset":name,"valid":all(c["passed"] for c in checks),"dataset_sha256":_sha(dataset),"record_sha256":_sha(records or []),"record_count":len(records or []) if isinstance(records,list) else 0,"checks":checks}


def dataset_lineage(name:str)->dict:
    dataset=get_dataset(name)
    if dataset is None:return {"dataset":name,"lineage":[],"error":"not found"}
    return {"dataset":name,"lineage":[{"name":name,"version":dataset.get("version"),"parent_version":dataset.get("parent_version"),"source":dataset.get("source"),"citation":dataset.get("citation"),"sha256":_sha(dataset)}]}


def snapshot_dataset(name:str,target_dir:str)->dict:
    dataset=get_dataset(name)
    if dataset is None:raise ValueError(f"unknown dataset '{name}'")
    os.makedirs(target_dir,exist_ok=True); records=dataset.get("records") or []
    records_path=os.path.join(target_dir,f"{name}_records.json")
    with open(records_path,"w",encoding="utf-8") as f:json.dump(records,f,indent=2,sort_keys=True)
    manifest={"schema":"bionexus-dataset-snapshot/v2","dataset":name,"source_version":dataset.get("version"),"parent_version":dataset.get("parent_version"),"type":dataset.get("type"),"date":dataset.get("date"),"category":dataset.get("category"),"source":dataset.get("source"),"citation":dataset.get("citation"),"ground_truth":dataset.get("ground_truth"),"record_count":len(records),"dataset_sha256":_sha(dataset),"records_sha256":_sha(records),"snapshotted_at":_iso_now()}
    manifest["manifest_sha256"]=_sha(manifest); manifest_path=os.path.join(target_dir,"manifest.json")
    with open(manifest_path,"w",encoding="utf-8") as f:json.dump(manifest,f,indent=2,sort_keys=True)
    return {"dataset":name,"record_count":len(records),"target":target_dir,"records_path":records_path,"manifest_path":manifest_path,"dataset_sha256":manifest["dataset_sha256"],"records_sha256":manifest["records_sha256"],"manifest_sha256":manifest["manifest_sha256"],"snapshotted_at":manifest["snapshotted_at"]}
