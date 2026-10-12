"""Generate a publication-oriented supplementary-material manifest.

The generator does not fabricate missing files. Each supplement is emitted with
an explicit availability state so a manuscript can distinguish present,
planned and unavailable material.
"""
from __future__ import annotations

from typing import Any


SUPPLEMENTS = [
    ("S1", "Benchmark datasets", "benchmark_datasets"),
    ("S2", "External validation results", "validation_results"),
    ("S3", "Containers and environments", "containers"),
    ("S4", "Raw analysis outputs", "raw_outputs"),
    ("S5", "Raw and source figures", "raw_figures"),
    ("S6", "Detailed methods", "methods"),
    ("S7", "Configuration files", "configuration"),
    ("S8", "Algorithm and tool parameters", "parameters"),
    ("S9", "AI prompts and evidence traces", "ai_prompts"),
    ("S10", "Software and database version manifest", "version_manifest"),
    ("S11", "Failure analysis and excluded cases", "failure_analysis"),
    ("S12", "Statistical analysis plan and raw statistics", "statistics"),
]


def build_supplementary_manifest(assets: dict[str, Any] | None = None) -> dict:
    assets = assets or {}
    rows = []
    available = 0
    for sid, title, key in SUPPLEMENTS:
        value = assets.get(key)
        is_available = value not in (None, "", [], {})
        if is_available:
            available += 1
        rows.append({
            "id": sid,
            "title": title,
            "asset_key": key,
            "status": "available" if is_available else "missing",
            "content": value if is_available else None,
            "reviewer_note": None if is_available else "Required for a complete high-impact submission; not yet supplied.",
        })
    return {
        "schema": "bionexus-supplementary-material/v1",
        "supplement_count": len(rows),
        "available_count": available,
        "complete": available == len(rows),
        "supplements": rows,
        "policy": "Missing supplements remain explicitly marked missing. The generator never substitutes synthetic data for unavailable validation or raw outputs.",
    }


def manuscript_checklist(manifest: dict) -> dict:
    supplements = manifest.get("supplements") or []
    missing = [s.get("id") for s in supplements if s.get("status") != "available"]
    return {
        "ready_for_full_supplementary_deposit": len(missing) == 0,
        "missing_supplements": missing,
        "available_supplements": [s.get("id") for s in supplements if s.get("status") == "available"],
    }
