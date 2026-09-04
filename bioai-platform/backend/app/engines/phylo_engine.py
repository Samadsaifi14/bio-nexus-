"""Phylogeny Engine — fourth reference engine (Component 5).

Parses the pipeline's canonical phylo result (app.routers.pipeline_v2, the
"phylo" step stores {"phylotree_newick": newick}) into a scientific object,
validates basic Newick well-formedness, exports JSON/Newick/CSV, and renders a
ladderized cladogram SVG (topology only, branch lengths not drawn) with zero
binary dependencies.

A missing tree (local-MAFFT path or failed step) is carried through the parser
and fails validation loudly — never a silent pass.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from app.engines.base import BaseEngine, EngineResult, ValidationReport

_LEAF_RE = re.compile(r"\b([^\s(),:]+)\s*:")


def _newick_leaves(newick: str | None) -> list[str]:
    """Ordered leaf labels in a Newick string (name immediately before ':').

    Returns the naive fallback [] (not an exception) for non-Newick input.
    """
    if not newick:
        return []
    return list(dict.fromkeys(_LEAF_RE.findall(newick)))


def _newick_balance(newick: str | None) -> int:
    """Net parenthesis balance; negative means more closes than opens."""
    if not newick:
        return 0
    depth = 0
    for ch in newick:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return depth
    return depth


class PhyloEngine(BaseEngine):
    name = "phylo"
    version = "1.0.0"
    tool = "Newick phylo (EBI ClustalO guide tree)"
    tool_version = None
    databases = ["SWISS-PROT homologs"]
    parameters = {
        "method": "guide tree from EBI MSA (Clustal Omega)",
        "input": "phylotree produced by the MSA stage",
        "notes": "topology-only rendering; branch lengths are not drawn",
    }
    citations = [
        "Sievers F, Higgins DG. Clustal Omega for making accurate alignments of many protein sequences. Protein Sci 27:135-145, 2018.",
        "Felsenstein J. PHYLIP - Phylogeny Inference Package. Cladistics 5:164-166, 1989.",
        "Madeira F, et al. Search and sequence analysis tools services from EMBL-EBI in 2022. Nucleic Acids Res 50:W276-W279, 2022.",
    ]
    benchmarks: list[str] = []
    export_formats = ["json", "csv", "newick"]

    def parse(self, raw: Any) -> EngineResult:
        if not isinstance(raw, dict):
            raise ValueError("cannot parse: phylo result must be an object")
        if "phylotree_newick" not in raw:
            raise ValueError("cannot parse: not a canonical phylo result (missing phylotree_newick)")
        newick = raw.get("phylotree_newick")
        leaves = _newick_leaves(newick)
        stats: dict[str, Any] = {
            "leaf_count": len(leaves),
            "newick_length": len(newick) if newick else 0,
            "balanced": _newick_balance(newick) == 0,
        }
        evidence: dict[str, Any] = {
            "phylotree_newick": newick,
            "leaves": leaves,
            "error": raw.get("error"),
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
        newick = evidence.get("phylotree_newick")
        error = evidence.get("error")
        checks = [
            {"name": "engine", "passed": result.engine == self.name, "detail": result.engine},
            {"name": "tool", "passed": bool(result.tool), "detail": result.tool},
            {"name": "database", "passed": bool(result.database), "detail": result.database},
            {"name": "error_free", "passed": not error, "detail": str(error or "ok")},
            {"name": "tree_present", "passed": bool(newick and str(newick).strip()), "detail": str(newick)[:60] if newick else "missing"},
        ]
        if newick:
            checks.append({
                "name": "newick_well_formed",
                "passed": str(newick).strip().startswith("(") and str(newick).strip().rstrip(";").endswith(")") and _newick_balance(newick) == 0,
                "detail": f"leaves={len(_newick_leaves(newick))}, balance={_newick_balance(newick)}",
            })
            checks.append({
                "name": "has_leaf_labels",
                "passed": bool(_newick_leaves(newick)),
                "detail": ", ".join(_newick_leaves(newick)[:6]),
            })
        return ValidationReport(checks, self.name)

    def _export_csv(self, result: EngineResult) -> str:
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["tree", "leaves", "newick"])
        newick = evidence.get("phylotree_newick") or ""
        writer.writerow([len(_newick_leaves(newick)), "|".join(_newick_leaves(newick)), newick])
        return buf.getvalue()

    def export(self, result: EngineResult, fmt: str = "json") -> str:
        if fmt == "newick":
            evidence = result.evidence if isinstance(result.evidence, dict) else {}
            return evidence.get("phylotree_newick") or ""
        return super().export(result, fmt)

    def figure(self, result: EngineResult) -> str:
        """Ladderized horizontal cladogram (topology only, equal branch lengths)."""
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        leaves = _newick_leaves(evidence.get("phylotree_newick"))
        n = len(leaves)
        if n == 0:
            return (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<svg xmlns="http://www.w3.org/2000/svg" width="520" height="120" viewBox="0 0 520 120">'
                '<rect width="520" height="120" fill="#ffffff"/>'
                '<text x="20" y="40" font-size="13" fill="#555">No phylogenetic tree available</text></svg>'
            )
        row_h = 24
        h = max(140, 70 + n * row_h)
        unit = 26
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="{h}" viewBox="0 0 640 {h}" font-family="Helvetica,Arial,sans-serif">',
            f'<rect width="640" height="{h}" fill="#ffffff"/>',
            f'<text x="20" y="30" font-size="16" font-weight="bold" fill="#111">Phylogeny — topology only, {n} leaves</text>',
        ]
        first_y = 56
        last_y = 56 + (n - 1) * row_h
        spine_x = 60
        parts.append(
            f'<line x1="{spine_x}" y1="{first_y - 8}" x2="{spine_x}" y2="{last_y + 8}" '
            f'stroke="#2b6cb0" stroke-width="1.5"/>'
        )
        for i, leaf in enumerate(leaves):
            y = 56 + i * row_h
            leaf_x = spine_x + 10 + unit * i
            parts.append(f'<line x1="{spine_x}" y1="{y}" x2="{leaf_x}" y2="{y}" stroke="#2b6cb0" stroke-width="1.5"/>')
            parts.append(f'<text x="{leaf_x + 8}" y="{y + 4}" font-size="12" fill="#333">{self._esc(leaf[:26])}</text>')
        parts.append(
            f'<text x="20" y="{h - 16}" font-size="10" fill="#888">Generated by BioNexus Phylo Engine '
            f'v{self.version} ({result.created_at}) · branch lengths not drawn</text>'
        )
        parts.append("</svg>")
        return "\n".join(parts)


phylo_engine = PhyloEngine()