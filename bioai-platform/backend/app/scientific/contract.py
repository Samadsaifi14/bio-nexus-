"""Common ``ScientificResult`` contract for every BioNexus scientific backend.

One shape, one rule:

* Every backend scientific module returns a ``ScientificResult``.
* The frontend renders what the backend emitted.  It never invents,
  recalculates, renames or silently substitutes scientific values.
* ``output_sha256`` is computed from the canonical JSON of the emitted payload,
  so any consumer can verify the payload was not mutated in transit.

Status semantics
----------------
``VALID``          the requested scientific analysis completed with the
                   requested method and no fallback substitution occurred.
``DEGRADED``       the analysis completed, but a component degraded (e.g. a
                   different engine/algorithm produced the result).  The
                   ``fallback_used`` / ``fallback_method`` and ``method`` fields
                   must describe exactly what produced the result.
``NOT_EVALUATED``  the capability has no measured validation evidence yet.
``FAILED``         the requested analysis could not complete; scientific
                   processing stopped.  Never fabricate results in this state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.services.evidence_policy import EvidenceClass


class ScientificStatus(str, Enum):
    VALID = "VALID"
    DEGRADED = "DEGRADED"
    NOT_EVALUATED = "NOT_EVALUATED"
    FAILED = "FAILED"


def canonical_json(obj: Any) -> str:
    """Deterministic JSON serialization for hashing and comparison."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def sha256_hex(data: bytes | bytearray | str) -> str:
    """SHA-256 hex digest of UTF-8 bytes (strings are encoded first)."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


_PAYLOAD_KEYS = (
    "status",
    "method",
    "engine",
    "engine_version",
    "database",
    "database_version",
    "parameters",
    "input_sha256",
    "fallback_used",
    "fallback_method",
    "results",
    "plots",
    "artifacts",
    "evidence_class",
    "validation",
    "citations",
)


@dataclass
class ScientificResult:
    """Canonical envelope returned by every scientific backend.

    ``results``, ``plots`` and ``artifacts`` are emitted by the backend exactly
    as produced; consumers render them without reinterpretation.
    """

    status: ScientificStatus
    method: str
    engine: str
    engine_version: str | None = None
    database: str | None = None
    database_version: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    input_sha256: str = ""
    output_sha256: str = ""
    fallback_used: bool = False
    fallback_method: str | None = None
    results: dict[str, Any] = field(default_factory=dict)
    plots: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    evidence_class: str = EvidenceClass.DETERMINISTIC.value
    validation: dict[str, Any] = field(default_factory=dict)
    citations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self, *, output_sha256: str | None = None) -> dict[str, Any]:
        """Serialize to the wire format (output_sha256 ignored when hashing)."""
        return {
            "status": self.status.value,
            "method": self.method,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "database": self.database,
            "database_version": self.database_version,
            "parameters": self.parameters,
            "input_sha256": self.input_sha256,
            "output_sha256": output_sha256 if output_sha256 is not None else self.output_sha256,
            "fallback_used": self.fallback_used,
            "fallback_method": self.fallback_method,
            "results": self.results,
            "plots": self.plots,
            "artifacts": self.artifacts,
            "evidence_class": self.evidence_class,
            "validation": self.validation,
            "citations": self.citations,
        }

    def compute_output_sha256(self) -> str:
        """Hash the emitted payload excluding the (self-referential) hash field."""
        body = self.to_dict(output_sha256="")
        return sha256_hex(canonical_json(body))

    def finalized(self) -> "ScientificResult":
        """Return a copy with ``output_sha256`` populated from its own payload."""
        return build_result(
            status=self.status,
            method=self.method,
            engine=self.engine,
            engine_version=self.engine_version,
            database=self.database,
            database_version=self.database_version,
            parameters=self.parameters,
            input_sha256=self.input_sha256 or _hash_parameters(self.parameters),
            fallback_used=self.fallback_used,
            fallback_method=self.fallback_method,
            results=self.results,
            plots=self.plots,
            artifacts=self.artifacts,
            evidence_class=self.evidence_class,
            validation=self.validation,
            citations=self.citations,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScientificResult":
        return cls(
            status=ScientificStatus(data["status"]),
            method=data["method"],
            engine=data["engine"],
            engine_version=data.get("engine_version"),
            database=data.get("database"),
            database_version=data.get("database_version"),
            parameters=data.get("parameters") or {},
            input_sha256=data.get("input_sha256", ""),
            output_sha256=data.get("output_sha256", ""),
            fallback_used=bool(data.get("fallback_used", False)),
            fallback_method=data.get("fallback_method"),
            results=data.get("results") or {},
            plots=data.get("plots") or [],
            artifacts=data.get("artifacts") or [],
            evidence_class=data.get("evidence_class", EvidenceClass.DETERMINISTIC.value),
            validation=data.get("validation") or {},
            citations=data.get("citations") or [],
        )


def _hash_parameters(parameters: dict[str, Any]) -> str:
    """Hash the parameter block when no explicit input hash is supplied."""
    return sha256_hex(canonical_json(parameters or {}))


def build_result(
    *,
    status: ScientificStatus,
    method: str,
    engine: str,
    engine_version: str | None = None,
    database: str | None = None,
    database_version: str | None = None,
    parameters: dict[str, Any] | None = None,
    input_sha256: str = "",
    input_data: str | bytes | None = None,
    fallback_used: bool = False,
    fallback_method: str | None = None,
    results: dict[str, Any] | None = None,
    plots: list[dict[str, Any]] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    evidence_class: str = EvidenceClass.DETERMINISTIC.value,
    validation: dict[str, Any] | None = None,
    citations: list[dict[str, Any]] | None = None,
) -> ScientificResult:
    """Build a finalized ``ScientificResult`` with hashes computed.

    ``input_sha256`` wins over ``input_data``; if neither is provided the hash
    is derived from the parameters block.  ``output_sha256`` is always computed
    from the emitted payload so consumers can verify integrity.
    """
    if not input_sha256:
        if input_data is not None:
            input_sha256 = sha256_hex(input_data)
        else:
            input_sha256 = _hash_parameters(parameters or {})

    result = ScientificResult(
        status=status,
        method=method,
        engine=engine,
        engine_version=engine_version,
        database=database,
        database_version=database_version,
        parameters=parameters or {},
        input_sha256=input_sha256,
        fallback_used=bool(fallback_used),
        fallback_method=fallback_method if fallback_used else None,
        results=results or {},
        plots=plots or [],
        artifacts=artifacts or [],
        evidence_class=evidence_class,
        validation=validation or {},
        citations=citations or [],
    )
    result.output_sha256 = result.compute_output_sha256()
    return result