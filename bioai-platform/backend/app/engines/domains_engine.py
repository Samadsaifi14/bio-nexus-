"""Domains Engine — fifth reference engine (Component 5).

Parses the pipeline's canonical InterPro domain result (app.tools.
domain_analysis.fetch_interpro_domains -> normalized shape) into a scientific
object, validates domain geometry (sorted, start<=end), exports JSON/CSV, and
renders a classic domain-architecture SVG map with zero binary dependencies.

A failed step (error + empty domains) is carried through and fails validation
loudly — never a silent pass.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from typing import Any

from app.engines.base import BaseEngine, EngineResult, ValidationReport

_DB_COLORS = {
    "PFAM": "#2b6cb0",
    "SMART": "#2f855a",
    "PROSITE": "#b7791f",
    "CDD": "#805ad5",
    "PANTHER": "#c53030",
    "PRINTS": "#4a5568",
    "HAMAP": "#2c7a7b",
    "COILS": "#6b46c1",
}


class DomainsEngine(BaseEngine):
    name = "domains"
    version = "1.0.0"
    tool = "InterPro"
    tool_version = None
    databases = ["InterPro (Pfam, SMART, PROSITE, CDD, PANTHER, PRINTS, HAMAP)"]
    parameters = {
        "lookup": "InterPro entry lookup by UniProt accession",
        "output": "domain architecture: db, name, start, end, score",
    }
    citations = [
        "Paysan-Lafosse T, et al. InterPro in 2022. Nucleic Acids Res 51:D418-D427, 2023.",
        "Mistry J, et al. Pfam: The protein families database in 2021. Nucleic Acids Res 49:D412-D419, 2021.",
        "de Castro E, et al. ScanProsite: detection of PROSITE signature matches. Nucleic Acids Res 34:W362-W365, 2006.",
    ]
    benchmarks: list[str] = []
    export_formats = ["json", "csv"]

    def parse(self, raw: Any) -> EngineResult:
        if not isinstance(raw, dict):
            raise ValueError("cannot parse: domains result must be an object")
        if "domains" not in raw or "uniprot_accession" not in raw:
            raise ValueError("cannot parse: not a canonical domains result (missing domains/uniprot_accession)")
        domains = raw.get("domains") or []
        for d in domains:
            d.setdefault("score", None)
        db_counts = Counter(str(d.get("source_db", "")).upper() for d in domains)
        covered = sum(max(0, int(d["end"]) - int(d["start"]) + 1) for d in domains if isinstance(d.get("start"), int) and isinstance(d.get("end"), int))
        stats: dict[str, Any] = {
            "domain_count": len(domains),
            "sequence_length": raw.get("sequence_length") or 0,
            "residues_covered": covered,
            "source_databases": sorted(db_counts),
        }
        evidence: dict[str, Any] = {
            "uniprot_accession": raw.get("uniprot_accession"),
            "sequence_length": raw.get("sequence_length") or 0,
            "domains": domains,
            "error": raw.get("error"),
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
        domains = evidence.get("domains") or []
        error = evidence.get("error")
        checks = [
            {"name": "engine", "passed": result.engine == self.name, "detail": result.engine},
            {"name": "tool", "passed": bool(result.tool), "detail": result.tool},
            {"name": "database", "passed": bool(result.database), "detail": result.database},
            {"name": "error_free", "passed": not error, "detail": str(error or "ok")},
            {"name": "accession_present", "passed": bool(evidence.get("uniprot_accession")), "detail": str(evidence.get("uniprot_accession"))},
            {"name": "sequence_length", "passed": isinstance(evidence.get("sequence_length"), int) and evidence.get("sequence_length", 0) >= 0, "detail": str(evidence.get("sequence_length"))},
        ]
        starts = [int(d.get("start", 0)) for d in domains]
        sorted_ok = starts == sorted(starts)
        geometry_ok = all(
            (d.get("start") is None and d.get("end") is None) or
            (isinstance(d.get("start"), int) and isinstance(d.get("end"), int) and d["start"] <= d["end"])
            for d in domains
        )
        checks.append({"name": "domains_sorted", "passed": sorted_ok, "detail": f"{len(domains)} domains"})
        checks.append({"name": "domain_geometry", "passed": geometry_ok, "detail": "start<=end for all" if geometry_ok else "invalid span"})
        return ValidationReport(checks, self.name)

    def _export_csv(self, result: EngineResult) -> str:
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["uniprot_accession", "source_db", "accession", "name", "start", "end", "score"])
        for d in evidence.get("domains") or []:
            writer.writerow([
                evidence.get("uniprot_accession"),
                d.get("source_db"),
                d.get("accession"),
                d.get("name"),
                d.get("start"),
                d.get("end"),
                d.get("score"),
            ])
        return buf.getvalue()

    def figure(self, result: EngineResult) -> str:
        """Classic domain-architecture map: sequence track + colored domain blocks."""
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        domains = evidence.get("domains") or []
        seq_len = evidence.get("sequence_length") or 0
        w, track_h = 820, 34
        header = 60
        rows = 1 if len(domains) <= 18 else (len(domains) // 12) + 1
        h = header + track_h * rows + 46
        base_y = header + track_h // 2
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Helvetica,Arial,sans-serif">',
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
            f'<text x="20" y="30" font-size="16" font-weight="bold" fill="#111">Domain architecture — {self._esc(evidence.get("uniprot_accession"))}, {len(domains)} domains</text>',
            f'<text x="20" y="50" font-size="12" fill="#444">Sequence length {seq_len} aa</text>',
        ]
        if seq_len > 0:
            track_x, track_w = 40, 700
            parts.append(f'<line x1="{track_x}" y1="{base_y}" x2="{track_x + track_w}" y2="{base_y}" stroke="#888" stroke-width="8" stroke-linecap="round"/>')
            for i, d in enumerate(domains):
                start = int(d.get("start", 0))
                end = int(d.get("end", 0))
                x1 = track_x + max(0, start) / seq_len * track_w
                x2 = track_x + max(0, end) / seq_len * track_w
                color = _DB_COLORS.get(str(d.get("source_db", "")).upper(), "#718096")
                label = f'{d.get("name", "")} ({d.get("accession", "")})'
                parts.append(f'<rect x="{x1}" y="{base_y - 12}" width="{max(x2 - x1, 4)}" height="24" fill="{color}" rx="3"/>')
                if x2 - x1 > 90:
                    parts.append(f'<text x="{min(x1 + 4, track_x + track_w - 6)}" y="{base_y + 4}" font-size="9" fill="#fff" font-weight="bold">{self._esc(str(label)[:36])}</text>')
        parts.append(
            f'<text x="20" y="{h - 18}" font-size="10" fill="#888">Generated by BioNexus Domains Engine '
            f'v{self.version} ({result.created_at}) · source databases: {", ".join(result.statistics.get("source_databases") or [])}</text>'
        )
        parts.append("</svg>")
        return "\n".join(parts)


domains_engine = DomainsEngine()