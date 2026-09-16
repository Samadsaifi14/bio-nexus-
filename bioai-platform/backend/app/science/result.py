"""Authoritative result contract for BioNexus scientific backends.

The scientific backend owns every reported value.  Frontends may format these
values but must not recompute, rename, fill, or silently substitute them.
"""

from __future__ import annotations

import hashlib
import json
import math
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ScientificStatus(str, Enum):
    VALID = "VALID"
    DEGRADED = "DEGRADED"
    NOT_EVALUATED = "NOT_EVALUATED"
    FAILED = "FAILED"


class ScientificResult(BaseModel):
    status: ScientificStatus
    method: str
    engine: str
    engine_version: str
    database: str | None = None
    database_version: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    input_sha256: str
    output_sha256: str

    fallback_used: bool = False
    fallback_method: str | None = None

    results: dict[str, Any] = Field(default_factory=dict)
    plots: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)

    evidence_class: str
    validation: dict[str, Any] = Field(default_factory=dict)
    citations: list[Any] = Field(default_factory=list)


def _json_default(value: Any) -> str:
    return str(value)


def _assert_finite(value: Any, path: str = "$" ) -> None:
    """Reject non-finite numbers before they can reach tables/plots/exports."""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"ScientificResult contains non-finite value at {path}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_finite(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_finite(item, f"{path}[{index}]")


def canonical_bytes(value: Any) -> bytes:
    _assert_finite(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    ).encode("utf-8")


def sha256_of(value: Any) -> str:
    if isinstance(value, bytes):
        data = value
    elif isinstance(value, str):
        data = value.encode("utf-8")
    else:
        data = canonical_bytes(value)
    return hashlib.sha256(data).hexdigest()


def build_scientific_result(
    *,
    status: ScientificStatus | str,
    method: str,
    engine: str,
    engine_version: str,
    input_payload: Any,
    results: dict[str, Any] | None = None,
    database: str | None = None,
    database_version: str | None = None,
    parameters: dict[str, Any] | None = None,
    fallback_used: bool = False,
    fallback_method: str | None = None,
    plots: list[dict[str, Any]] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    evidence_class: str = "Deterministic computation",
    validation: dict[str, Any] | None = None,
    citations: list[Any] | None = None,
) -> dict[str, Any]:
    """Build and hash one scientific result without altering emitted values."""
    status_value = ScientificStatus(status)
    result_values = results or {}
    plot_values = plots or []
    artifact_values = artifacts or []
    parameter_values = parameters or {}
    validation_values = validation or {}
    citation_values = citations or []

    output_basis = {
        "status": status_value.value,
        "method": method,
        "engine": engine,
        "engine_version": engine_version,
        "database": database,
        "database_version": database_version,
        "parameters": parameter_values,
        "fallback_used": bool(fallback_used),
        "fallback_method": fallback_method,
        "results": result_values,
        "plots": plot_values,
        "artifacts": artifact_values,
        "evidence_class": evidence_class,
        "validation": validation_values,
        "citations": citation_values,
    }

    model = ScientificResult(
        **output_basis,
        input_sha256=sha256_of(input_payload),
        output_sha256=sha256_of(output_basis),
    )
    return model.model_dump(mode="json")


def failed_scientific_result(
    *,
    method: str,
    engine: str,
    engine_version: str,
    input_payload: Any,
    reason: str,
    parameters: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    database: str | None = None,
    database_version: str | None = None,
    citations: list[Any] | None = None,
) -> dict[str, Any]:
    """Return a terminal scientific failure.  No downstream result is implied."""
    validation_payload = dict(validation or {})
    validation_payload.update({"scientific_processing_stopped": True, "reason": reason})
    return build_scientific_result(
        status=ScientificStatus.FAILED,
        method=method,
        engine=engine,
        engine_version=engine_version,
        database=database,
        database_version=database_version,
        input_payload=input_payload,
        parameters=parameters,
        results={},
        plots=[],
        artifacts=[],
        evidence_class="Unsupported/insufficient evidence",
        validation=validation_payload,
        citations=citations or [],
    )
