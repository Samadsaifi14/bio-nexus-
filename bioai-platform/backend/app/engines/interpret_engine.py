"""Interpret Engine — eighth reference engine (Component 5).

Parses the pipeline's canonical AI-interpretation result (app.ai.interpreter.
interpret_text -> {"interpretation": str}) into a scientific object and
validates it under the honest-AI acceptance criteria: a report is either real
text, or an explicit availability banner — never silent fabrication. Exports
JSON/TXT and renders a report summary SVG with zero binary dependencies.
"""

from __future__ import annotations

from typing import Any

from app.engines.base import BaseEngine, EngineResult, ValidationReport

HONEST_BANNERS = (
    "AI interpretation unavailable:",
    "All AI providers failed.",
)


class InterpretEngine(BaseEngine):
    name = "interpret"
    version = "1.0.0"
    tool = "LLM interpretation"
    tool_version = None
    databases: list[str] = []  # AI synthesis has no target database
    parameters = {
        "provider_chain": "Groq -> Gemini -> Ollama (fallback, retries)",
        "temperature": 0.3,
        "max_tokens": 2000,
        "honesty": "failure yields an explicit banner, never fabricated analysis",
    }
    citations = [
        "BioNexus honest-AI acceptance criteria (MASTER_PLAN): an unexecuted or failed LLM pass displays a visible banner, never fake analysis.",
    ]
    benchmarks: list[str] = []
    export_formats = ["json", "txt"]

    def parse(self, raw: Any) -> EngineResult:
        if not isinstance(raw, dict):
            raise ValueError("cannot parse: interpret result must be an object")
        if "interpretation" not in raw:
            raise ValueError("cannot parse: not a canonical interpret result (missing interpretation)")
        text = raw.get("interpretation")
        if not isinstance(text, str):
            raise ValueError("cannot parse: interpretation must be a string")
        is_banner = text.startswith(HONEST_BANNERS)
        stats: dict[str, Any] = {
            "char_count": len(text),
            "word_count": len(text.split()),
            "honest_banner": is_banner,
            "is_report": bool(text) and not is_banner,
        }
        evidence: dict[str, Any] = {
            "interpretation": text,
            "honest_banner": is_banner,
        }
        return EngineResult(
            engine=self.name,
            tool=self.tool,
            statistics=stats,
            evidence=evidence,
        )

    def validate(self, result: EngineResult) -> ValidationReport:
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        text = evidence.get("interpretation") or ""
        banner = evidence.get("honest_banner")
        checks = [
            {"name": "engine", "passed": result.engine == self.name, "detail": result.engine},
            {"name": "tool", "passed": bool(result.tool), "detail": result.tool},
            {"name": "interpretation_present", "passed": bool(text), "detail": "missing" if not text else f"{len(text)} chars"},
            {"name": "not_fabricated_empty", "passed": bool(text), "detail": "empty report rejected" if not text else "report present"},
        ]
        if text:
            if banner:
                checks.append({
                    "name": "honest_failure_banner",
                    "passed": True,
                    "detail": text[:70],
                })
            else:
                checks.append({
                    "name": "report_not_placeholder",
                    "passed": len(text.strip()) > 0 and not text.startswith(HONEST_BANNERS),
                    "detail": f"{len(text.split())} words",
                })
        return ValidationReport(checks, self.name)

    def export(self, result: EngineResult, fmt: str = "json") -> str:
        if fmt == "txt":
            evidence = result.evidence if isinstance(result.evidence, dict) else {}
            return str(evidence.get("interpretation") or "")
        return super().export(result, fmt)

    def figure(self, result: EngineResult) -> str:
        """Report summary card — first 220 chars of the interpretation."""
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        text = str(evidence.get("interpretation") or "")
        preview = text[:220].replace("\n", " ")
        w, h = 640, 240
        color = "#b7791f" if evidence.get("honest_banner") else "#2f855a"
        kind = "Availability banner" if evidence.get("honest_banner") else "AI interpretation"
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Helvetica,Arial,sans-serif">',
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
            f'<text x="20" y="30" font-size="16" font-weight="bold" fill="#111">{kind} — {len(text.split())} words</text>',
            f'<rect x="20" y="46" width="600" height="10" fill="{color}" opacity="0.85"/>',
            f'<text x="20" y="86" font-size="12" fill="#333">{self._esc(preview)}</text>',
        ]
        if not text:
            parts.append('<text x="20" y="120" font-size="12" fill="#c53030">Empty report — no interpretation captured.</text>')
        parts.append(f'<text x="20" y="{h - 18}" font-size="10" fill="#888">Generated by BioNexus Interpret Engine v{self.version} ({result.created_at}) · honesty: banners, never fabrication</text>')
        parts.append("</svg>")
        return "\n".join(parts)


interpret_engine = InterpretEngine()