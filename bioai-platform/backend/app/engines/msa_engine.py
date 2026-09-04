"""MSA Engine — third reference engine (Component 5).

Parses the pipeline's canonical MSA result (app.routers.pipeline_v2._run_msa)
into a scientific object, validates the alignment invariant (every row the
same aligned length), exports JSON/CSV/FASTA, and renders a conservation SVG
figure with zero binary dependencies.

A failed MSA step is part of the canonical shape (error + null aln_fasta): the
parser carries it through and the validator fails loudly — never a silent pass.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from app.engines.base import BaseEngine, EngineResult, ValidationReport


def parse_alignment_fasta(aln_fasta: str | None) -> list[tuple[str, str]]:
    """Split an aligned FASTA block into (header, row) records, keeping order."""
    records: list[tuple[str, str]] = []
    if not aln_fasta:
        return records
    current: tuple[str, list[str]] | None = None
    for line in aln_fasta.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current:
                records.append((current[0], "".join(current[1]).upper()))
            current = (line[1:].split()[0], [])
        elif current is not None:
            current[1].append(line)
    if current:
        records.append((current[0], "".join(current[1]).upper()))
    return records


class MSAEngine(BaseEngine):
    name = "msa"
    version = "1.0.0"
    tool = "MSA"
    tool_version = None
    databases = ["SWISS-PROT homologs"]
    parameters = {
        "methods": ["mafft-local", "EBI ClustalO/MAFFT/Kalign/MUSCLE/T-Coffee", "in-process fallback"],
        "mode": "global (or local refinement of the top hit)",
        "selection": "top 5 BLAST hits + query",
    }
    citations = [
        "Katoh K, Standley DM. MAFFT Multiple Sequence Alignment Software Version 7. Mol Biol Evol 30:772-780, 2013.",
        "Sievers F, Higgins DG. Clustal Omega for making accurate alignments of many protein sequences. Protein Sci 27:135-145, 2018.",
        "Madeira F, et al. Search and sequence analysis tools services from EMBL-EBI in 2022. Nucleic Acids Res 50:W276-W279, 2022.",
    ]
    # Benchmarks for MSA are not yet in the seed catalog; keep honest and empty.
    benchmarks: list[str] = []
    export_formats = ["json", "csv", "fasta"]

    def parse(self, raw: Any) -> EngineResult:
        if not isinstance(raw, dict):
            raise ValueError("cannot parse: MSA result must be an object")
        if "aln_fasta" not in raw:
            raise ValueError("cannot parse: not a canonical MSA result (missing aln_fasta)")
        aln = raw.get("aln_fasta")
        records = parse_alignment_fasta(aln)
        seq = records[0][1] if records else ""
        stats: dict[str, Any] = {
            "sequence_count": raw.get("sequence_count"),
            "aligned_columns": len(seq) if seq else 0,
            "method": raw.get("method"),
            "fallback": raw.get("_fallback", False),
            "alignment_mode": raw.get("alignment_mode"),
            "has_phylotree": bool(raw.get("phylotree")),
        }
        evidence: dict[str, Any] = {
            "alignment": aln,
            "phylotree": raw.get("phylotree"),
            "method": raw.get("method"),
            "fallback": raw.get("_fallback", False),
            "alignment_mode": raw.get("alignment_mode"),
            "error": raw.get("error"),
            "pairwise_subject": (raw.get("pairwise") or {}).get("subject"),
        }
        return EngineResult(
            engine=self.name,
            tool=raw.get("method") or self.tool,
            database=self.databases[0],
            input_ref=f"{raw.get('sequence_count')} sequences",
            statistics=stats,
            evidence=evidence,
            parameters={"alignment_mode": raw.get("alignment_mode")},
        )

    def validate(self, result: EngineResult) -> ValidationReport:
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        aln = evidence.get("alignment")
        records = parse_alignment_fasta(aln)
        error = evidence.get("error")
        checks = [
            {"name": "engine", "passed": result.engine == self.name, "detail": result.engine},
            {"name": "tool", "passed": bool(result.tool), "detail": result.tool},
            {"name": "database", "passed": bool(result.database), "detail": result.database},
            {"name": "error_free", "passed": not error, "detail": str(error or "ok")},
            {"name": "alignment_fasta_present", "passed": bool(aln), "detail": f"{len(records)} aligned rows"},
        ]
        if not error and records:
            checks.append({
                "name": "sequence_count_at_least_2",
                "passed": len(records) >= 2,
                "detail": f"{len(records)} rows",
            })
            lengths = sorted({len(seq) for _, seq in records})
            checks.append({
                "name": "aligned_rows_equal_length",
                "passed": len(lengths) == 1,
                "detail": "=".join(str(x) for x in lengths) if lengths else "none",
            })
        return ValidationReport(checks, self.name)

    def _export_csv(self, result: EngineResult) -> str:
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        records = parse_alignment_fasta(evidence.get("alignment"))
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["seq_id", "aligned_length", "aligned_sequence"])
        for seq_id, seq in records:
            writer.writerow([seq_id, len(seq), seq])
        return buf.getvalue()

    def export(self, result: EngineResult, fmt: str = "json") -> str:
        if fmt == "fasta":
            evidence = result.evidence if isinstance(result.evidence, dict) else {}
            aln = evidence.get("alignment") or ""
            return aln
        return super().export(result, fmt)

    def figure(self, result: EngineResult) -> str:
        """Conservation track (identity vs the first/query row) as a compact SVG."""
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        records = parse_alignment_fasta(evidence.get("alignment"))
        stat = result.statistics if isinstance(result.statistics, dict) else {}
        w, h, plot_w, plot_h = 760, 240, 660, 120
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Helvetica,Arial,sans-serif">',
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
            f'<text x="20" y="32" font-size="16" font-weight="bold" fill="#111">MSA — {self._esc(stat.get("method"))}, {self._esc(str(stat.get("sequence_count")))} sequences, {self._esc(str(stat.get("aligned_columns")))} columns</text>',
        ]
        if records:
            ref = records[0][1]
            plot_x, plot_y = 76, 66
            parts.append(f'<text x="20" y="{plot_y + 60}" font-size="10" fill="#333">Row label — {self._esc(records[0][0])}, conservation vs query</text>')
            ys = [plot_y + 6 + (26 * i) for i in range(len(records))]
            for i, (sid, seq) in enumerate(records):
                parts.append(f'<text x="20" y="{ys[i]}" font-size="10" fill="#333">{self._esc(sid[:28])}</text>')
            for col in range(len(ref)):
                x = plot_x + col
                conserved = all(seq[col] == ref[col] for _, seq in records[1:] if col < len(seq))
                color = "#2f855a" if conserved else "#cbd5e0"
                for i, (sid, seq) in enumerate(records):
                    if col >= len(seq):
                        continue
                    head = f'<rect x="{x}" y="{ys[i] - 6}" width="1" height="12" fill="{color}"/>'
                    parts.append(head)
        stat_text = f'fallback={bool(stat.get("fallback"))} · phylotree={bool(stat.get("has_phylotree"))}'
        parts.append(f'<text x="20" y="{h - 18}" font-size="10" fill="#888">Generated by BioNexus MSA Engine v{self.version} ({result.created_at}) · {stat_text}</text>')
        parts.append("</svg>")
        return "\n".join(parts)


msa_engine = MSAEngine()