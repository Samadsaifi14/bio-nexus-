"""NGS Engine (BioNexus 2.0, Component 11).

Wraps the production NGS pipeline (FastQC -> alignment QC -> variant calling
-> annotation) under the independent-engine contract: parse the pipeline report
into a canonical scientific object, validate its QC/variant invariants, export
JSON/CSV and render a QC figure.

Canonical input (the flattened per-run pipeline report):

    {
      "assay": "WGS", "reference": "grch38",
      "reads_analyzed": 200, "all_records_processed": true,
      "synthetic_reference": false,
      "validation": {"passed": true, "warnings": [...]},
      "stages": {
        "raw_read_qc":   {"q30_pct": 92.1, "gc_pct": 41.2},
        "alignment_qc":  {"mapping_rate": 0.99},
        "variant_calling": {"variants": 5, "snps": 4, "indels": 1}
      }
    }
"""

from __future__ import annotations

from typing import Any

from app.engines.base import BaseEngine, EngineResult, ValidationReport
from app.figure.engine import bar_chart_panel, esc


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class NGSEngine(BaseEngine):
    name = "ngs"
    version = "1.0.0"
    tool = "NGS production pipeline (manual mode / Sarek-style DAG)"
    tool_version = None
    databases = ["FASTQ (interpretation)", "grch38/hg38"]
    parameters = {
        "stages": "FastQC -> MultiQC(anomaly) -> alignment QC -> variant calling -> normalization -> QC -> filtering",
        "qc_thresholds": {"q30_min": 80.0, "gc_range": [0, 100], "mapping_min": 0.5},
        "demo_profiles": ["tumor-exome", "germline-wgs", "rna-tumor", "humanized"],
        "input_note": "raw results are a compact demonstration/positive control unless all_records_processed",
    }
    citations = [
        "Andrews S. FastQC: A Quality Control tool for High Throughput Sequence Data. Babraham Bioinformatics.",
        "Li H. Aligning sequence reads, clone sequences and assembly contigs with BWA-MEM. arXiv:1303.3997, 2013.",
        "Van der Auwera GA, O'Connor BD. Genomics in the Cloud. O'Reilly, 2020 (GATK best practices).",
    ]
    benchmarks = ["NGS_FASTQC_Q30_ABOVE_THRESHOLD"]
    export_formats = ["json", "csv"]

    def parse(self, raw: Any) -> EngineResult:
        if not isinstance(raw, dict):
            raw = {}
        stages = raw.get("stages") or {}
        qqc = stages.get("raw_read_qc") or {}
        aqc = stages.get("alignment_qc") or {}
        vc = stages.get("variant_calling") or {}
        reads = raw.get("reads_analyzed", 0)
        return EngineResult(
            engine=self.name,
            tool=self.tool,
            database=self.databases[0],
            input_ref=f"reads={reads} {raw.get('assay', '?')} vs {raw.get('reference', '?')}",
            statistics={
                "reads_analyzed": int(reads or 0),
                "q30_pct": _num(qqc.get("q30_pct", qqc.get("q30"))),
                "gc_pct": _num(qqc.get("gc_pct", qqc.get("gc"))),
                "mapping_rate": _num(aqc.get("mapping_rate", aqc.get("mapping_pct", 0))),
                "mapping_as_pct": _num(aqc.get("mapping_rate", 0)) * 100,
                "variant_count": int(vc.get("variants", 0) or 0),
                "snps": int(vc.get("snps", 0) or 0),
                "indels": int(vc.get("indels", 0) or 0),
                "all_records_processed": bool(raw.get("all_records_processed")),
            },
            evidence={
                "validation": raw.get("validation") or {},
                "warnings": raw.get("warnings") or [],
                "synthetic_reference": bool(raw.get("synthetic_reference")),
                "demo": bool(raw.get("demo")),
            },
            parameters={"assay": raw.get("assay"), "reference": raw.get("reference")},
        )

    def validate(self, result: EngineResult) -> ValidationReport:
        checks = super().validate(result).checks
        s = result.statistics
        q30 = s["q30_pct"]
        gc = s["gc_pct"]
        mapping = s["mapping_rate"]
        reads = s["reads_analyzed"]

        checks.extend([
            {"name": "reads_present", "passed": reads > 0, "detail": f"{reads} reads"},
            {"name": "q30_bounded", "passed": 0 < q30 <= 100, "detail": f"Q30={q30:.1f}%"},
            {"name": "gc_bounded", "passed": 0 <= gc <= 100, "detail": f"GC={gc:.1f}%"},
            {"name": "mapping_bounded", "passed": 0 <= mapping <= 1.000001, "detail": f"mapping={mapping:.4f}"},
            {"name": "variant_count_nonnegative", "passed": s["variant_count"] >= 0, "detail": f"{s['variant_count']} variants"},
            {
                "name": "honest_input_scope",
                "passed": bool(s["all_records_processed"]) or bool(result.evidence.get("demo")),
                "detail": "every record processed, or explicitly a demonstration/preview",
            },
        ])
        return ValidationReport(checks, self.name)

    def _export_csv(self, result: EngineResult) -> str:
        s = result.statistics
        header = "metric,value"
        rows = [
            header,
            f"reads_analyzed,{s['reads_analyzed']}",
            f"q30_pct,{s['q30_pct']:.1f}",
            f"gc_pct,{s['gc_pct']:.1f}",
            f"mapping_rate,{s['mapping_rate']:.4f}",
            f"variant_count,{s['variant_count']}",
            f"snps,{s['snps']}",
            f"indels,{s['indels']}",
        ]
        return "\n".join(rows)

    def figure(self, result: EngineResult) -> str:
        s = result.statistics
        rows = [
            ("Reads analyzed (n)", float(s["reads_analyzed"])),
            ("Q30 bases %", s["q30_pct"]),
            ("GC content %", s["gc_pct"]),
        ]
        canvas = bar_chart_panel(rows, x=30, y=60, w=300, h=260, value_label="")
        mapping = s["mapping_rate"]
        header = (
            f'<text x="30" y="30" font-size="14" font-weight="bold" fill="#111827">NGS QC summary</text>'
            f'<text x="30" y="50" font-size="10" fill="#6b7280">mapping rate {mapping * 100:.1f}% · variants {s["variant_count"]} (snps {s["snps"]}, indels {s["indels"]})</text>'
        )
        footer = f'<text x="30" y="420" font-size="9" fill="#6b7280">Generated by BioNexus NGS Engine v{self.version}</text>'
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="380" height="440" '
            'viewBox="0 0 380 440" font-family="Helvetica, Arial, sans-serif">'
            '<rect x="0" y="0" width="380" height="440" fill="#ffffff" rx="8"/>'
            f"{header}{canvas}{footer}</svg>"
        )


ngs_engine = NGSEngine()