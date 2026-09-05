"""AlphaFold Engine — sixth reference engine (Component 5).

Parses the pipeline's canonical AlphaFold result (app.tools.alphafold
AlphaFoldTool; de novo path = app.services.de_novo.esmfold_structure) into a
scientific object, validates structure claims (pLDDT bounds, URL/accession
consistency when a structure is claimed), exports JSON/CSV, and renders a
summary SVG with zero binary dependencies.

No-prediction outcomes (404, de novo failure) are valid, honest results — the
engine never claims a structure exists when the data doesn't say so.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from app.engines.base import BaseEngine, EngineResult, ValidationReport


def _int_or_none(v: Any) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


class AlphaFoldEngine(BaseEngine):
    name = "alphafold"
    version = "1.0.0"
    tool = "AlphaFold"
    tool_version = None
    databases = ["AlphaFold DB"]
    parameters = {
        "lookup": "AlphaFold DB by UniProt accession",
        "de_novo": "ESMFold ab initio when resolution is unavailable",
        "confidence_metric": "mean pLDDT (0-100)",
    }
    citations = [
        "Jumper J, et al. Highly accurate protein structure prediction with AlphaFold. Nature 596:583-589, 2021.",
        "Varadi M, et al. AlphaFold Protein Structure Database in 2024. Nucleic Acids Res 52:D368-D375, 2024.",
        "Lin Z, et al. Evolutionary-scale prediction of atomic-level protein structure with a language model. Science 379:1123-1130, 2023.",
    ]
    benchmarks = [
        "PDB_TP53_STRUCTURE_AVAILABLE",
        "ALPHAFOLD_TP53_AVAILABLE",
        "ALPHAFOLD_INSULIN_AVAILABLE",
    ]
    export_formats = ["json", "csv"]

    def parse(self, raw: Any) -> EngineResult:
        if not isinstance(raw, dict):
            raise ValueError("cannot parse: alphafold result must be an object")
        if "structure_available" not in raw:
            raise ValueError("cannot parse: not a canonical alphafold result (missing structure_available)")
        source = raw.get("source") or ("esmfold" if raw.get("pdb_text") else "alphafold_db")
        confidence = raw.get("confidence")
        stats: dict[str, Any] = {
            "structure_available": bool(raw.get("structure_available")),
            "confidence": confidence,
            "model_created_date": raw.get("model_created_date"),
            "latest_version": _int_or_none(raw.get("latest_version")),
            "source": source,
        }
        evidence: dict[str, Any] = {
            "uniprot_accession": raw.get("uniprot_accession"),
            "structure_available": bool(raw.get("structure_available")),
            "confidence": confidence,
            "pdb_url": raw.get("pdb_url"),
            "cif_url": raw.get("cif_url"),
            "model_created_date": raw.get("model_created_date"),
            "latest_version": _int_or_none(raw.get("latest_version")),
            "message": raw.get("message"),
            "error": raw.get("error"),
            "source": source,
        }
        return EngineResult(
            engine=self.name,
            tool=self.tool,
            database=self.databases[0],
            input_ref=raw.get("uniprot_accession"),
            statistics=stats,
            evidence=evidence,
        )

    def validate(self, result: EngineResult) -> ValidationReport:
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        available = evidence.get("structure_available") is True
        confidence = evidence.get("confidence")
        checks = [
            {"name": "engine", "passed": result.engine == self.name, "detail": result.engine},
            {"name": "tool", "passed": bool(result.tool), "detail": result.tool},
            {"name": "database", "passed": bool(result.database), "detail": result.database},
            {"name": "structure_availability_declared", "passed": isinstance(evidence.get("structure_available"), bool), "detail": str(available)},
        ]
        if confidence is not None:
            checks.append({
                "name": "confidence_bounded_0_100",
                "passed": isinstance(confidence, (int, float)) and 0 <= float(confidence) <= 100,
                "detail": str(confidence),
            })
        if available:
            pdb = evidence.get("pdb_url") or ""
            accession = evidence.get("uniprot_accession") or ""
            checks.append({
                "name": "pdb_url_consistent",
                "passed": pdb.startswith("https://") and (not accession or accession in pdb or f"AF-{accession}" in pdb),
                "detail": pdb,
            })
        return ValidationReport(checks, self.name)

    def _export_csv(self, result: EngineResult) -> str:
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["uniprot_accession", "structure_available", "confidence", "source", "pdb_url"])
        writer.writerow([
            evidence.get("uniprot_accession"),
            evidence.get("structure_available"),
            evidence.get("confidence"),
            evidence.get("source"),
            evidence.get("pdb_url"),
        ])
        return buf.getvalue()

    def figure(self, result: EngineResult) -> str:
        """Summary card: structure badge, pLDDT, model metadata."""
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        available = evidence.get("structure_available") is True
        confidence = evidence.get("confidence")
        source = evidence.get("source")
        acc = evidence.get("uniprot_accession")
        w, h = 620, 300
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Helvetica,Arial,sans-serif">',
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
            f'<text x="20" y="30" font-size="16" font-weight="bold" fill="#111">Structure — {self._esc(acc or "n/a")}</text>',
        ]
        if available:
            badge_color = "#2f855a"
            badge = f"Structure available · pLDDT {confidence if confidence is not None else 'n/a'}"
        else:
            badge_color = "#b7791f"
            badge = f"No structure available ({self._esc(source or 'n/a')})"
        parts.append(f'<rect x="20" y="52" width="560" height="46" rx="6" fill="{badge_color}"/>')
        parts.append(f'<text x="36" y="80" font-size="14" font-weight="bold" fill="#fff">{self._esc(badge)}</text>')
        y = 128
        for label, value in (
            ("Source", source or "n/a"),
            ("Model created", evidence.get("model_created_date") or "n/a"),
            ("Latest version", str(evidence.get("latest_version") or "n/a")),
            ("PDB URL", (evidence.get("pdb_url") or "n/a")[:70]),
            ("Message", (evidence.get("message") or "n/a")[:70]),
        ):
            parts.append(f'<text x="20" y="{y}" font-size="12" fill="#334"><tspan font-weight="bold">{self._esc(label)}</tspan>: {self._esc(value)}</text>')
            y += 24
        parts.append(f'<text x="20" y="{h - 18}" font-size="10" fill="#888">Generated by BioNexus AlphaFold Engine v{self.version} ({result.created_at})</text>')
        parts.append("</svg>")
        return "\n".join(parts)


alphafold_engine = AlphaFoldEngine()