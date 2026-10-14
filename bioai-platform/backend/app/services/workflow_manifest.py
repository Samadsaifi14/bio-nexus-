"""Portable evidence export. No workflow adapter or execution is implied."""
from __future__ import annotations

import hashlib
import json


_STATES = {"complete": "COMPLETED", "completed": "COMPLETED", "failed": "FAILED",
           "skipped": "SKIPPED", "running": "RUNNING", "queued": "QUEUED",
           "pending": "NOT_EXECUTED"}


def build_workflow_manifest(experiment: dict, provenance: list[dict]) -> dict:
    """Export stored evidence without synthesizing versions or scientific results."""
    nodes = []
    gaps = []
    for field in ("input_hash", "git_commit", "container_hash"):
        if not experiment.get(field):
            gaps.append({"node": None, "field": field, "reason": "NOT_RECORDED"})
    for index, source in enumerate(provenance):
        node_id = source.get("node_id") or source.get("id")
        if not node_id:
            node_id = f"unidentified-record-{index}"
            gaps.append({"node": node_id, "field": "node_id", "reason": "NOT_RECORDED"})
        raw_status = source.get("status")
        node = {"id": node_id, "recorded_status": raw_status,
                "state": _STATES.get(raw_status, "UNKNOWN"),
                "tool": source.get("tool"), "tool_version": source.get("tool_version"),
                "database": source.get("database"), "database_version": source.get("database_version"),
                "parameters": source.get("params"), "depends_on": source.get("deps") or [],
                "input_ref": source.get("input_ref"), "output_ref": source.get("output_ref"),
                "completed_at": source.get("completed_at"), "evidence": source.get("evidence")}
        nodes.append(node)
        if node["state"] == "COMPLETED":
            for field in ("tool", "tool_version", "completed_at"):
                if not node[field]:
                    gaps.append({"node": node_id, "field": field, "reason": "NOT_RECORDED"})
            if node["database"] and not node["database_version"]:
                gaps.append({"node": node_id, "field": "database_version", "reason": "NOT_RECORDED"})
    ids = {node["id"] for node in nodes}
    if len(ids) != len(nodes):
        gaps.append({"node": None, "field": "node_id", "reason": "DUPLICATE_ID"})
    edges = []
    for node in nodes:
        for dependency in node["depends_on"]:
            edges.append({"from": dependency, "to": node["id"]})
            if dependency not in ids:
                gaps.append({"node": node["id"], "field": "depends_on", "reason": "UNRECORDED_DEPENDENCY", "dependency": dependency})
    if not nodes:
        gaps.append({"node": None, "field": "steps", "reason": "NOT_RECORDED"})
    manifest = {"format": "bionexus-workflow-evidence", "schema_version": 1,
                "execution": {"executable": False, "adapter": None,
                              "statement": "Evidence export only; no tools are launched and external workflow compatibility has not been validated."},
                "experiment_id": experiment.get("experiment_id"), "job_id": experiment.get("job_id"),
                "pipeline": experiment.get("pipeline"), "recorded_status": experiment.get("status"),
                "input_sha256": experiment.get("input_hash"), "output_sha256": experiment.get("output_hash"),
                "git_commit": experiment.get("git_commit"), "container_hash": experiment.get("container_hash"),
                "software_versions": experiment.get("software_versions"), "database_versions": experiment.get("database_versions"),
                "environment": experiment.get("environment"), "random_seed": experiment.get("random_seed"),
                "parameters": experiment.get("parameters"), "started_at": experiment.get("started_at"),
                "finished_at": experiment.get("finished_at"), "steps": nodes, "edges": edges,
                "reproducibility_gaps": gaps,
                "integrity": {"algorithm": "sha256", "serialization": "JSON sorted keys, UTF-8, compact separators; manifest_sha256 excluded"}}
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    manifest["manifest_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return manifest
