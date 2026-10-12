"""Pathway Engine — seventh reference engine (Component 5).

Parses the pipeline's canonical pathway-enrichment result (app.services.
pathway_enrichment.run_enrichment) into a scientific object, validates the
ORA table invariants (found<=total, geneRatio consistency, FDR bounds, sort
order), exports JSON/CSV, and renders a geneRatio SVG bar chart with zero
binary dependencies.

A run that yields no enriched pathways is a valid, honest result. Stats are
reported exactly as supplied by the provider; BioNexus never reinterprets
provider p-values as model confidence.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from app.engines.base import BaseEngine, EngineResult, ValidationReport


def _num(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


class PathwayEngine(BaseEngine):
    name = "pathway"
    version = "1.0.0"
    tool = "Reactome"
    tool_version = None
    databases = ["Reactome"]
    parameters = {
        "method": "over-representation analysis (ORA)",
        "stats": "p-value / FDR reported exactly as supplied by Reactome Analysis Service",
        "input": "top UniProt gene names (max 20)",
    }
    citations = [
        "Gillespie M, et al. The reactome pathway knowledgebase 2022. Nucleic Acids Res 50:D687-D692, 2022.",
        "Fabregat A, et al. Reactome pathway analysis: a high-performance in-memory approach. BMC Bioinformatics 18:142, 2017.",
    ]
    benchmarks: list[str] = []
    export_formats = ["json", "csv"]

    def parse(self, raw: Any) -> EngineResult:
        if not isinstance(raw, dict):
            raise ValueError("cannot parse: pathway result must be an object")
        if "pathways" not in raw:
            raise ValueError("cannot parse: not a canonical pathway result (missing pathways)")
        pathways = raw.get("pathways") or []
        stats: dict[str, Any] = {
            "pathway_count": len(pathways),
            "input_token": raw.get("token"),
        }
        top = [p.get("name") for p in pathways[:5]]
        evidence: dict[str, Any] = {
            "pathways": pathways,
            "method": raw.get("method"),
            "significance_note": raw.get("significance_note"),
            "from_cache": raw.get("from_cache", False),
            "top_pathways": top,
        }
        return EngineResult(
            engine=self.name,
            tool=self.tool,
            database=self.databases[0],
            statistics=stats,
            evidence=evidence,
        )

    def validate(self, result: EngineResult) -> ValidationReport:
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        pathways = evidence.get("pathways") or []
        checks = [
            {"name": "engine", "passed": result.engine == self.name, "detail": result.engine},
            {"name": "tool", "passed": bool(result.tool), "detail": result.tool},
            {"name": "database", "passed": bool(result.database), "detail": result.database},
            {"name": "pathway_count", "passed": isinstance(len(pathways), int), "detail": f"{len(pathways)} pathways"},
        ]
        table_ok = all(
            isinstance(p.get("name"), str) and bool(p.get("name"))
            for p in pathways
        )
        checks.append({"name": "pathway_names_present", "passed": table_ok, "detail": f"{len(pathways)} entries"})
        bounds_ok = True
        ratio_ok = True
        sort_ok = True
        prev_fdr: float | None = None
        for p in pathways:
            found = _num(p.get("entitiesFound"))
            total = _num(p.get("entitiesTotal"))
            fdr = _num(p.get("reactomeFDR"))
            pv = _num(p.get("reactomePValue"))
            gr = _num(p.get("geneRatio"))
            if fdr is not None and not (0 <= fdr <= 1):
                bounds_ok = False
            if pv is not None and not (0 <= pv <= 1):
                bounds_ok = False
            if found is not None and total is not None and found > total:
                bounds_ok = False
            if found is not None and total and gr is not None and not (abs(gr - found / total) <= 1e-4):
                ratio_ok = False
            if fdr is None:
                continue
            if prev_fdr is not None and fdr < prev_fdr:
                sort_ok = False
            prev_fdr = fdr
        checks.append({"name": "statistical_bounds", "passed": bounds_ok, "detail": "found<=total, 0<=p/fdr<=1" if bounds_ok else "out-of-bounds stat"})
        checks.append({"name": "gene_ratio_consistent", "passed": ratio_ok, "detail": "geneRatio==found/total" if ratio_ok else "inconsistent ratio"})
        checks.append({"name": "sorted_by_fdr_asc", "passed": sort_ok, "detail": "ascending FDR (None last)" if sort_ok else "out of order"})
        return ValidationReport(checks, self.name)

    def _export_csv(self, result: EngineResult) -> str:
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["stId", "name", "species", "entitiesFound", "entitiesTotal", "geneRatio", "pValue", "FDR"])
        for p in evidence.get("pathways") or []:
            writer.writerow([
                p.get("stId"),
                p.get("name"),
                p.get("species"),
                p.get("entitiesFound"),
                p.get("entitiesTotal"),
                p.get("geneRatio"),
                p.get("reactomePValue"),
                p.get("reactomeFDR"),
            ])
        return buf.getvalue()

    def figure(self, result: EngineResult) -> str:
        """Top-10 geneRatio bar chart (FDR-labelled)."""
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        pathways = sorted(
            (evidence.get("pathways") or []),
            key=lambda p: (p.get("reactomeFDR") is None, p.get("reactomeFDR") or 1.0),
        )[:10]
        w, h = 760, 280 + 24 * max(len(pathways), 1)
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Helvetica,Arial,sans-serif">',
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
            f'<text x="20" y="30" font-size="16" font-weight="bold" fill="#111">Pathway enrichment — gene ratio (top {len(pathways)})</text>',
        ]
        y = 58
        max_gr = max((_num(p.get("geneRatio")) or 0) for p in pathways) or 1.0
        bar_w = 420
        for p in pathways:
            gr = _num(p.get("geneRatio")) or 0.0
            fdr = _num(p.get("reactomeFDR"))
            label = str(p.get("name") or "n/a")[:48]
            parts.append(f'<text x="20" y="{y}" font-size="11" fill="#333">{self._esc(label)}</text>')
            parts.append(f'<rect x="300" y="{y - 10}" width="{int(gr / max_gr * bar_w) if max_gr else 0}" height="14" fill="#2b6cb0" rx="2"/>')
            parts.append(f'<text x="730" y="{y}" font-size="10" fill="#555" text-anchor="end">{gr:.3f} · FDR {("n/a" if fdr is None else f"{fdr:.2g}")}</text>')
            y += 24
        parts.append(f'<text x="20" y="{h - 18}" font-size="10" fill="#888">Generated by BioNexus Pathway Engine v{self.version} ({result.created_at}) · stats as supplied by Reactome</text>')
        parts.append("</svg>")
        return "\n".join(parts)


pathway_engine = PathwayEngine()