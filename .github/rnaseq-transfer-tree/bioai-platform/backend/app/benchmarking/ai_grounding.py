"""Claim-safe wrapper around deterministic BBS-2 AI grounding checks."""

from __future__ import annotations

from typing import Any

from app.benchmarking.bbs2 import evaluate_ai_bundle


def evaluate_grounding(payload: dict[str, Any]) -> dict[str, Any]:
    result = evaluate_ai_bundle(payload)
    grounding_passed = bool(result.get("passed"))
    result.update(
        {
            "grounding_passed": grounding_passed,
            "scientifically_validated": False,
            "biological_truth_established": False,
            "validation_scope": "RECORDED_EVIDENCE_CORRESPONDENCE_ONLY",
            "scope_note": (
                "Passing numeric, citation and unsupported-claim checks establishes correspondence "
                "to the supplied recorded evidence. It is not independent scientific or biological validation."
            ),
        }
    )
    return result
