"""BLAST Engine — reference bioinformatics engine (Component 5).

Parses the pipeline's canonical BLAST result (NCBI XML parser or EBI tool,
normalized by app.routers.pipeline_v2._build_blast_result) into the scientific
object, validates it, exports JSON/CSV, and renders an SVG figure with zero
binary dependencies (matplotlib is not required).
"""

from __future__ import annotations

import csv
import io
from typing import Any

from app.engines.base import BaseEngine, EngineResult, ValidationReport

STATISTIC_KEYS = ("count", "query_length", "top_hit_identity", "top_hit_evalue", "top_hit_bit_score")
MISSING_HIT_CHECK = {"name": "top_hit_present", "passed": False, "detail": "count > 0 but no top_hit"}


class BLASTEngine(BaseEngine):
    name = "blast"
    version = "1.0.0"
    tool = "BLAST"
    tool_version = None
    databases = ["nr", "swissprot", "pdb", "pdb_nr", "refseq_protein", "env_nr", "nt", "refseq_rna"]
    parameters = {
        "program": ["blastp", "blastn", "blastx", "tblastn"],
        "max_hits": "5-100",
        "fallback_rule": "EBI first, then NCBI",
    }
    citations = [
        "Altschul S.F. et al. Basic Local Alignment Search Tool. J Mol Biol 215(3):403-410, 1990.",
        "Camacho C. et al. BLAST+: architecture and applications. BMC Bioinformatics 10:421, 2009.",
        "Madeira F. et al. Search and sequence analysis tools services from EMBL-EBI in 2022. Nucleic Acids Res, 2022.",
    ]
    benchmarks = [
        "INSULIN_SWISSPROT_TOP_HIT",
        "HUMAN_TP53_SWISSPROT_TOP_HIT",
        "HUMAN_TP53_NOT_INSULIN",
        "HUMAN_OXTR_SWISSPROT_TOP_HIT",
        "HUMAN_HBB_SWISSPROT_TOP_HIT",
    ]

    def parse(self, raw: Any) -> EngineResult:
        """Normalize the canonical BLAST result dict into a scientific object."""
        if "hits" not in raw or "count" not in raw:
            raise ValueError("cannot parse: not a canonical BLAST result (missing hits/count)")
        top = raw.get("top_hit") or {}
        hits = raw.get("hits") or []
        stats: dict[str, Any] = {
            "count": raw.get("count"),
            "query_length": raw.get("query_length"),
            "top_hit_identity": top.get("identity_pct"),
            "top_hit_evalue": top.get("evalue_raw") or top.get("evalue"),
            "top_hit_bit_score": top.get("bit_score"),
        }
        evidence: dict[str, Any] = {
            "source": raw.get("source"),
            "program": raw.get("program"),
            "query_sequence_type": raw.get("query_sequence_type"),
            "query_accession": raw.get("query_accession"),
            "top_hit": {
                "accession": top.get("accession"),
                "description": top.get("description"),
                "identity_pct": top.get("identity_pct"),
                "evalue": top.get("evalue_raw") or top.get("evalue"),
                "alignment_length": top.get("alignment_length"),
            } if top else None,
            "hits": hits[:10],
        }
        return EngineResult(
            engine=self.name,
            tool=self.tool,
            tool_version=None,
            database=raw.get("database"),
            input_ref=evidence.get("query_accession") or None,
            statistics=stats,
            evidence=evidence,
        )

    def validate(self, result: EngineResult) -> ValidationReport:
        checks = [
            {"name": "engine", "passed": result.engine == self.name, "detail": result.engine},
            {"name": "tool", "passed": bool(result.tool), "detail": result.tool},
            {"name": "database", "passed": bool(result.database), "detail": result.database},
        ]
        hits = (result.evidence.get("hits") or []) if isinstance(result.evidence, dict) else []
        count = result.statistics.get("count")
        top = result.evidence.get("top_hit") if isinstance(result.evidence, dict) else None
        checks.append({
            "name": "count",
            "passed": isinstance(count, int) and count >= 0,
            "detail": str(count),
        })
        if count not in (None, 0) and not top:
            checks.append(dict(MISSING_HIT_CHECK))
        if top:
            checks.append({
                "name": "top_hit_accession",
                "passed": bool(top.get("accession")),
                "detail": str(top.get("accession")),
            })
            ident = top.get("identity_pct")
            checks.append({
                "name": "top_hit_identity_range",
                "passed": isinstance(ident, (int, float)) and 0 <= ident <= 100,
                "detail": str(ident),
            })
        return ValidationReport(checks, self.name)

    def _export_csv(self, result: EngineResult) -> str:
        hits = (result.evidence.get("hits") or []) if isinstance(result.evidence, dict) else []
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["accession", "description", "evalue", "identity_pct", "bit_score", "alignment_length"],
            lineterminator="\n",
        )
        writer.writeheader()
        for h in hits:
            writer.writerow({
                "accession": h.get("accession", ""),
                "description": h.get("description", ""),
                "evalue": h.get("evalue_raw", h.get("evalue", "")),
                "identity_pct": h.get("identity_pct", ""),
                "bit_score": h.get("bit_score", ""),
                "alignment_length": h.get("alignment_length", ""),
            })
        return buf.getvalue()

    def figure(self, result: EngineResult) -> str:
        """Publication-style SVG: top-hit identity bars + p-values (no deps)."""
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        hits = (evidence.get("hits") or [])[:10]
        top = evidence.get("top_hit") or {}
        w, row_h = 860, 30
        title = "BLAST top hits — %s" % (result.database or "unknown database")
        h = 70 + max(len(hits), 1) * row_h + 40
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Helvetica,Arial,sans-serif">',
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
            f'<text x="20" y="36" font-size="18" font-weight="bold" fill="#111">{self._esc(title)}</text>',
        ]
        if not hits:
            parts.append(f'<text x="20" y="70" font-size="14" fill="#666">No hits returned.</text>')
        for i, hit in enumerate(hits):
            y = 66 + i * row_h
            ident = hit.get("identity_pct") or 0
            evalue = hit.get("evalue_raw", hit.get("evalue", ""))
            acc = str(hit.get("accession", ""))
            desc = str(hit.get("description", ""))[:34]
            bar_w = max(2, int(float(ident)) * 5)
            parts.append(f'<text x="20" y="{y + 4}" font-size="9" fill="#999">#{i + 1}</text>')
            parts.append(f'<rect x="42" y="{y - 12}" width="{bar_w}" height="14" fill="#2b6cb0"/>')
            parts.append(f'<text x="46" y="{y + 14}" font-size="12" fill="#222">{self._esc(acc)} {self._esc(desc)}</text>')
            parts.append(f'<text x="760" y="{y + 14}" font-size="11" fill="#555" text-anchor="end">id {ident:.1f}%  e {self._esc(evalue)}</text>' if isinstance(ident, float) else
                         f'<text x="760" y="{y + 14}" font-size="11" fill="#555" text-anchor="end">id {self._esc(ident)}  e {self._esc(evalue)}</text>')
        parts.append(f'<text x="20" y="{h - 20}" font-size="10" fill="#888">Generated by BioNexus BLAST Engine v{self.version} ({result.created_at})</text>')
        parts.append("</svg>")
        return "\n".join(parts)


blast_engine = BLASTEngine()