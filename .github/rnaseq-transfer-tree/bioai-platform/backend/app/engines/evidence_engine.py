"""Evidence Engine (BioNexus 2.0, Component 9).

Validates the evidence graph: every AI claim must carry evidence back to a
source (tool -> database -> version) or be explicitly rejected. Publication
informatics / AI-evidence honesty invariant — no silent unsupported claims.
"""

from __future__ import annotations

from typing import Any

from app.engines.base import BaseEngine, EngineResult, ValidationReport

CONFIDENCE_TIERS = ("high", "medium", "low")
REJECTED_CONFIDENCE = "none"


class EvidenceEngine(BaseEngine):
    name = "evidence"
    version = "1.1.0"
    tool = "Evidence Graph"
    tool_version = None
    databases = ["derived from provenance graph"]
    parameters = {
        "input": "evidence graph: sources + claims + edges",
        "source_identity": "static tool/database/version map per result section",
        "claim_linking": "keyword overlap between sentence and source vocabulary",
        "confidence": "high (2+ sources) / medium (1) / low (supported but weak); none is reserved for explicitly rejected claims",
        "honesty": "unsupported claims are marked rejected, never hidden",
    }
    citations = [
        "BioNexus AI Evidence Engine — claim-to-source provenance for AI interpretations.",
        "Wright K, et al. The Future of Clinical AI: Explainability. Nat Rev Nephrol 2021.",
    ]
    benchmarks: list[str] = []
    export_formats = ["json", "csv"]

    def parse(self, raw: Any) -> EngineResult:
        if not isinstance(raw, dict):
            raw = {}
        claims = raw.get("claims") or []
        sources = raw.get("sources") or []
        supported = sum(1 for c in claims if c.get("evidence"))
        rejected = sum(1 for c in claims if c.get("rejected"))
        return EngineResult(
            engine=self.name,
            tool=self.tool,
            database=self.databases[0],
            statistics={
                "claims": len(claims),
                "sources": len(sources),
                "supported": supported,
                "rejected": rejected,
                "unsupported": len(claims) - supported,
                "edges": len(raw.get("edges") or []),
                "typed_edges": len(raw.get("typed_edges") or []),
            },
            evidence={"graph": raw},
        )

    @staticmethod
    def _claim_confidence_valid(claim: dict) -> bool:
        """Admitted claims need an evidence confidence tier; rejected claims use none."""
        confidence = claim.get("confidence")
        if claim.get("rejected"):
            return confidence == REJECTED_CONFIDENCE
        return confidence in CONFIDENCE_TIERS

    def validate(self, result: EngineResult) -> ValidationReport:
        checks = super().validate(result).checks
        graph = result.evidence.get("graph") or {}
        sources = graph.get("sources") or []
        claims = graph.get("claims") or []

        source_ids = {s.get("id") for s in sources}
        bad_refs = set()
        for c in claims:
            for ref in (c.get("evidence") or []):
                if ref not in source_ids:
                    bad_refs.add(ref)

        checks.extend([
            {
                "name": "graph_nonempty",
                "passed": bool(sources) and bool(claims),
                "detail": f"{len(sources)} sources, {len(claims)} claims",
            },
            {
                "name": "claim_fields",
                "passed": all(c.get("text") and self._claim_confidence_valid(c) for c in claims),
                "detail": "admitted claims require high/medium/low confidence; explicitly rejected claims require confidence=none",
            },
            {
                "name": "source_fields",
                "passed": all(s.get("tool") and s.get("database") and s.get("version") for s in sources),
                "detail": f"{len(sources)} sources; each requires tool, database and version",
            },
            {
                "name": "honest_claims",
                "passed": all(c.get("evidence") or c.get("rejected") for c in claims),
                "detail": "every claim is supported or explicitly rejected",
            },
            {
                "name": "graph_reference",
                "passed": not bad_refs,
                "detail": (f"bad refs: {sorted(bad_refs)}" if bad_refs else "all evidence refs resolve to a source"),
            },
        ])
        return ValidationReport(checks, self.name)

    def _export_csv(self, result: EngineResult) -> str:
        graph = result.evidence.get("graph") or {}
        rows = ["claim_id,claim,confidence,evidence,rejected"]
        for c in graph.get("claims") or []:
            q = lambda s: '"' + str(s or "").replace('"', "'") + '"'
            rows.append(
                ",".join([
                    q(c.get("id")),
                    q(c.get("text")),
                    str(c.get("confidence", "")),
                    q(";".join(c.get("evidence") or [])),
                    str(bool(c.get("rejected"))).lower(),
                ])
            )
        return "\n".join(rows)

    def figure(self, result: EngineResult) -> str:
        graph = result.evidence.get("graph") or {}
        sources = graph.get("sources") or []
        claims = graph.get("claims") or []
        x = 20
        y = 40
        parts = [f'<text x="{x}" y="{y}" font-size="14" font-weight="bold" fill="#111827">AI evidence graph</text>']
        y += 24
        for s in sources:
            parts.append(
                f'<rect x="{x}" y="{y}" width="240" height="26" rx="4" fill="#2563eb" opacity="0.85"/>'
                f'<text x="{x + 10}" y="{y + 17}" font-size="11" fill="#ffffff">{self._esc(s.get("id"))} · {self._esc(s.get("tool"))} · {self._esc(s.get("version"))}</text>'
            )
            y += 34
        y += 10
        for c in claims:
            color = "#059669" if c.get("evidence") else "#dc2626"
            status = "supported" if c.get("evidence") else "rejected"
            parts.append(
                f'<text x="{x}" y="{y}" font-size="11" fill="{color}">&#9679; {self._esc(c.get("id"))} [{self._esc(c.get("confidence"))}] {status} · {self._esc(str(c.get("text"))[:64])}</text>'
            )
            y += 18
        parts.append(f'<text x="{x}" y="{y + 6}" font-size="10" fill="#6b7280">Generated by BioNexus Evidence Engine v{self.version}</text>')
        parts.append('<style>svg { background: #ffffff; } rect { stroke: none; }</style>')
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="{y + 40}" '
            f'viewBox="0 0 640 {y + 40}" font-family="Helvetica, Arial, sans-serif">' + "".join(parts) + "</svg>"
        )


evidence_engine = EvidenceEngine()
