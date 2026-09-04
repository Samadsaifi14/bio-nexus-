"""Objective workflow-fragmentation comparator for BioNexus and external platforms.

The tool deliberately does not invent usability scores.  Each platform is described by a
machine-readable evidence manifest containing observable actions required to complete the
same pre-specified task.  It reports counts only; subjective ease-of-use claims require a
human-participant study.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_ACTION_FIELDS = {"id", "kind", "description", "evidence"}
ALLOWED_KINDS = {"service_switch", "manual_transfer", "format_conversion", "parameter_entry", "execution", "export", "verification"}


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("platform") or not data.get("task") or not isinstance(data.get("actions"), list):
        raise ValueError(f"{path}: platform, task and actions are required")
    for i, action in enumerate(data["actions"]):
        missing = REQUIRED_ACTION_FIELDS - set(action)
        if missing: raise ValueError(f"{path}: action {i} missing {sorted(missing)}")
        if action["kind"] not in ALLOWED_KINDS: raise ValueError(f"{path}: unsupported action kind {action['kind']}")
        if not str(action["evidence"]).strip(): raise ValueError(f"{path}: every action requires an evidence note or URL")
    return data


def summarize(data: dict) -> dict:
    counts = {k: 0 for k in sorted(ALLOWED_KINDS)}
    for action in data["actions"]: counts[action["kind"]] += 1
    return {
        "platform": data["platform"], "task": data["task"], "protocol_version": data.get("protocol_version"),
        "action_count": len(data["actions"]), "counts": counts,
        "unique_external_services": len(set(data.get("external_services", []))),
        "intermediate_files": len(data.get("intermediate_files", [])),
        "evidence_complete": all(bool(a.get("evidence")) for a in data["actions"]),
    }


def main(a: Path, b: Path, output: Path) -> int:
    ma, mb = load_manifest(a), load_manifest(b)
    if ma["task"] != mb["task"]: raise ValueError("Manifests must evaluate exactly the same task")
    sa, sb = summarize(ma), summarize(mb)
    result = {
        "suite": "BBS-1 objective workflow burden comparison",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "task": ma["task"], "platforms": [sa, sb],
        "differences_b_minus_a": {
            "actions": sb["action_count"] - sa["action_count"],
            "service_switches": sb["counts"]["service_switch"] - sa["counts"]["service_switch"],
            "manual_transfers": sb["counts"]["manual_transfer"] - sa["counts"]["manual_transfer"],
            "format_conversions": sb["counts"]["format_conversion"] - sa["counts"]["format_conversion"],
            "intermediate_files": sb["intermediate_files"] - sa["intermediate_files"],
        },
        "claim_boundary": "These are protocol action counts, not usability, cognitive-load, speed, preference or productivity measurements. Human superiority claims require a prospective user study.",
    }
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("platform_a", type=Path); p.add_argument("platform_b", type=Path)
    p.add_argument("--output", type=Path, default=Path("results/workflow_burden.json"))
    x = p.parse_args(); raise SystemExit(main(x.platform_a, x.platform_b, x.output))
