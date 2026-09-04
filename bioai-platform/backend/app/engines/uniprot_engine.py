"""UniProt Engine — second reference engine (Component 5).

Parses the pipeline's canonical UniProt result (app.routers.pipeline_v2.
_run_uniprot) into a scientific object, validates it, exports JSON/CSV, and
renders a GO-category SVG figure with zero binary dependencies.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from typing import Any

from app.engines.base import BaseEngine, EngineResult, ValidationReport

SUBCELLULAR_KEY = "subcellular_locations"


class UniProtEngine(BaseEngine):
    name = "uniprot"
    version = "1.0.0"
    tool = "UniProt"
    tool_version = None
    databases = ["UniProtKB/Swiss-Prot", "UniProtKB/TrEMBL"]
    parameters = {
        "fields": ["accession", "full_name", "organism", "gene_names", "functions", "go_terms",
                   "keywords", "subcellular_locations", "pdb_ids", "features"],
        "resolution_ladder": "direct -> xref -> name search -> EBI sequence BLAST -> idmapping",
        "confidence_levels": ["identified", "homolog"],
    }
    citations = [
        "UniProt Consortium. UniProt: the Universal Protein Knowledgebase in 2023. Nucleic Acids Res 51:D523-D531, 2023.",
        "Ashburner M. et al. Gene Ontology: tool for the unification of biology. Nat Genet 25:25-29, 2000.",
        "The Gene Ontology Consortium. The Gene Ontology resource: enriching a GOld mine. Nucleic Acids Res 49:D325-D334, 2021.",
    ]
    benchmarks = [
        "UNIPROT_TP53_RETRIEVAL",
        "UNIPROT_INSULIN_RETRIEVAL",
        "UNIPROT_OXTR_RETRIEVAL",
        "UNIPROT_PSA_RETRIEVAL",
        "UNIPROT_P53_MUST_BE_TP53_GENE",
    ]
    export_formats = ["json", "csv"]

    def parse(self, raw: Any) -> EngineResult:
        if "accession" not in raw:
            raise ValueError("cannot parse: not a canonical UniProt result (missing accession)")
        go = raw.get("go_terms") or []
        features = raw.get("features") or []
        stats: dict[str, Any] = {
            "sequence_length": raw.get("sequence_length"),
            "go_count": len(go),
            "function_count": len(raw.get("functions") or []),
            "feature_count": len(features),
            "keyword_count": len(raw.get("keywords") or []),
            "subcellular_location_count": len(raw.get(SUBCELLULAR_KEY) or []),
            "pdb_id_count": len(raw.get("pdb_ids") or []),
        }
        resolution = raw.get("resolution") or {}
        evidence: dict[str, Any] = {
            "accession": raw.get("accession"),
            "full_name": raw.get("full_name"),
            "organism": raw.get("organism"),
            "gene_names": raw.get("gene_names") or [],
            "confidence": raw.get("confidence"),
            "resolved_uniprot": raw.get("resolved_uniprot"),
            "resolution": {"method": resolution.get("method"), "original_accession": resolution.get("original_accession")},
            "go_terms": go,
            "features": features[:10],
            "subcellular_locations": raw.get(SUBCELLULAR_KEY) or [],
        }
        return EngineResult(
            engine=self.name,
            tool=self.tool,
            database=raw.get("source") or "UniProtKB",
            input_ref=resolution.get("original_accession") or raw.get("accession"),
            statistics=stats,
            evidence=evidence,
        )

    def validate(self, result: EngineResult) -> ValidationReport:
        checks = [
            {"name": "engine", "passed": result.engine == self.name, "detail": result.engine},
            {"name": "tool", "passed": bool(result.tool), "detail": result.tool},
            {"name": "database", "passed": bool(result.database), "detail": result.database},
        ]
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        checks.append({
            "name": "accession",
            "passed": bool(evidence.get("accession")),
            "detail": str(evidence.get("accession")),
        })
        checks.append({
            "name": "sequence_length",
            "passed": isinstance(result.statistics.get("sequence_length"), int) and result.statistics.get("sequence_length") >= 0,
            "detail": str(result.statistics.get("sequence_length")),
        })
        for term in (evidence.get("go_terms") or []):
            if not (isinstance(term, str) and len(term) > 2 and term[0] in "CFP" and term[1] == ":"):
                checks.append({"name": "go_term_malformed", "passed": False, "detail": str(term)[:40]})
                break
        else:
            checks.append({"name": "go_term_format", "passed": True, "detail": f"{len(evidence.get('go_terms') or [])} GO terms"})
        return ValidationReport(checks, self.name)

    def _export_csv(self, result: EngineResult) -> str:
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["accession", "full_name", "organism", "category", "go_term"])
        for term in evidence.get("go_terms") or []:
            cat, _, name = term.partition(":")
            writer.writerow([evidence.get("accession"), evidence.get("full_name"), evidence.get("organism"), cat, name])
        return buf.getvalue()

    def figure(self, result: EngineResult) -> str:
        """Publication-style SVG: GO category distribution + sequence length."""
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        go = evidence.get("go_terms") or []
        counts = Counter()
        for term in go:
            cat = term[0] if isinstance(term, str) and term else "?"
            counts[cat] += 1
        labels = {"C": "Cellular component", "F": "Molecular function", "P": "Biological process"}
        w, h = 720, 260
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Helvetica,Arial,sans-serif">',
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
            f'<text x="20" y="34" font-size="17" font-weight="bold" fill="#111">UniProt GO annotation — {self._esc(evidence.get("accession"))} {self._esc(evidence.get("full_name"))}</text>',
        ]
        y = 64
        max_n = max(counts.values()) if counts else 0
        colors = {"C": "#2b6cb0", "F": "#2f855a", "P": "#b7791f"}
        for cat in ("C", "F", "P"):
            n = counts.get(cat, 0)
            label = self._esc(labels.get(cat, cat))
            bar_w = int(n / max_n * 460) if max_n else 0
            parts.append(f'<text x="20" y="{y + 4}" font-size="12" fill="#333">{label}</text>')
            parts.append(f'<rect x="260" y="{y - 11}" width="{max(bar_w, 1)}" height="16" fill="{colors[cat]}"/>')
            parts.append(f'<text x="740" y="{y + 4}" font-size="12" fill="#333" text-anchor="end">{n}</text>')
            y += 26
        seq_len = result.statistics.get("sequence_length") or 0
        parts.append(f'<text x="20" y="{y + 20}" font-size="12" fill="#555">Sequence length {self._esc(str(seq_len))} aa · confidence {self._esc(evidence.get("confidence"))}</text>')
        parts.append(f'<text x="20" y="{h - 18}" font-size="10" fill="#888">Generated by BioNexus {self.tool} Engine v{self.version} ({result.created_at})</text>')
        parts.append("</svg>")
        return "\n".join(parts)


uniprot_engine = UniProtEngine()