"""Scientific Data Layer (BioNexus 2.0, Component 4) — engine contract.

Every bioinformatics engine emits the *same* scientific object so results are
uniform across BLAST, UniProt, docking, MD, NGS, ... : metadata, version,
source, statistics, evidence, figures and exports. This is the spine the
Provenance Layer and the Export Layer build on.
"""

from __future__ import annotations

import html
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EngineResult:
    """The canonical scientific object every engine produces."""

    def __init__(
        self,
        *,
        engine: str,
        tool: str,
        tool_version: str | None = None,
        database: str | None = None,
        database_version: str | None = None,
        input_ref: str | None = None,
        output_ref: str | None = None,
        statistics: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
        figures: list[str] | None = None,
        exports: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        source: str = "engine",
    ):
        self.engine = engine
        self.tool = tool
        self.tool_version = tool_version
        self.database = database
        self.database_version = database_version
        self.input_ref = input_ref
        self.output_ref = output_ref
        self.statistics = statistics or {}
        self.evidence = evidence or {}
        self.figures = figures or []
        self.exports = exports or []
        self.parameters = parameters or {}
        self.source = source
        self.created_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "tool": self.tool,
            "tool_version": self.tool_version,
            "database": self.database,
            "database_version": self.database_version,
            "input_ref": self.input_ref,
            "output_ref": self.output_ref,
            "statistics": self.statistics,
            "evidence": self.evidence,
            "figures": self.figures,
            "exports": self.exports,
            "parameters": self.parameters,
            "source": self.source,
            "created_at": self.created_at,
        }


class ValidationReport:
    """Result of validating an EngineResult — used by automatic validation."""

    def __init__(self, checks: list[dict[str, Any]], engine: str):
        self.engine = engine
        self.checks = checks

    @property
    def valid(self) -> bool:
        return all(c["passed"] for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {"engine": self.engine, "valid": self.valid, "checks": self.checks}


class BaseEngine(ABC):
    """One independent engine (Component 5): Runner, Validator, Parser, Exporter,
    Citation, Figure generator, Benchmark reference, Tests."""

    name: str = ""
    version: str = ""
    tool: str = ""
    tool_version: str | None = None
    databases: list[str] = []
    parameters: dict[str, Any] = {}
    citations: list[str] = []
    benchmarks: list[str] = []
    export_formats: list[str] = ["json", "csv"]
    figure_formats: list[str] = ["svg"]

    @abstractmethod
    def parse(self, raw: Any) -> EngineResult:
        """Normalize a raw tool output into the canonical scientific object."""

    def validate(self, result: EngineResult) -> ValidationReport:
        """Return a validation report over the canonical result. Base checks the
        schema invariants; engines extend with domain rules."""
        checks = [
            {"name": "engine", "passed": result.engine == self.name, "detail": result.engine},
            {"name": "tool", "passed": bool(result.tool), "detail": result.tool},
            {"name": "database", "passed": bool(result.database), "detail": result.database},
        ]
        return ValidationReport(checks, self.name)

    def export(self, result: EngineResult, fmt: str = "json") -> str:
        """Serialize a result to the requested export format."""
        if fmt not in self.export_formats:
            raise ValueError(f"unsupported export format: {fmt}")
        if fmt == "csv":
            return self._export_csv(result)
        return self._export_json(result)

    def figure(self, result: EngineResult) -> str:
        """A publication-grade figure (SVG by default, no binary dependency)."""
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "tool": self.tool,
            "tool_version": self.tool_version,
            "databases": self.databases,
            "parameters": self.parameters,
            "citations": self.citations,
            "benchmarks": self.benchmarks,
            "export_formats": self.export_formats,
            "figure_formats": self.figure_formats,
        }

    # --- helpers ----------------------------------------------------------

    def _export_json(self, result: EngineResult) -> str:
        import json

        return json.dumps(result.to_dict(), indent=2)

    def _export_csv(self, result: EngineResult) -> str:
        raise NotImplementedError

    @staticmethod
    def _esc(text: str | None) -> str:
        return html.escape(str(text or ""), quote=True)