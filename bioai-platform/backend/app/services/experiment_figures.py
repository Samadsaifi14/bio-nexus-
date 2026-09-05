"""Experiment figure composer (Component 8).

Builds one multi-panel *publication figure* for a recorded experiment from its
stored result context. Pure SVG composition (no binary deps): each available
result section becomes a labeled panel with a statistical caption; a master
title, legend note and citation block make the whole canvas manuscript-ready.

The endpoint reads the job's stored context (context_json or storage artifact)
and calls ``build_experiment_figure``.
"""

from __future__ import annotations

from typing import Any

from app.figure.engine import (
    CELL_W,
    bar_chart_panel,
    domain_blocks_panel,
    esc,
    footer_block,
    panel_caption,
    panel_header,
    panel_xy,
    svg_canvas,
    svg_close,
    text_lines_panel,
    title_block,
    wrap_text,
)

CITATIONS = [
    "Camacho C, et al. BLAST+. BMC Bioinformatics 10:421, 2009; UniProt Consortium. Nucleic Acids Res 51:D523-D531, 2023.",
    "Paysan-Lafosse T, et al. InterPro in 2022. Nucleic Acids Res 51:D418-D427, 2023.",
    "Madeira F, et al. EMBL-EBI search & sequence analysis services in 2022. Nucleic Acids Res 50:W276-W279, 2022.",
    "Jumper J, et al. AlphaFold. Nature 596:583-589, 2021; Gillespie M, et al. Reactome 2022. Nucleic Acids Res 50:D687-D692.",
]


def _blast_panel(blast: dict, index: int) -> list[str]:
    hits = (blast.get("hits") or [])
    rows = []
    top = blast.get("top_hit") or {}
    if top and top.get("accession"):
        rows.append((f"{top['accession'][:8]} {esc(top.get('description') or '')[:24]}", float(top.get("identity_pct") or 0)))
    for h in hits[:5]:
        acc = h.get("accession") or "?"
        rows.append((f"{acc[:8]} {esc(h.get('description') or '')[:24]}", float(h.get("identity_pct") or 0)))
    x, y = panel_xy(index)
    body = bar_chart_panel(rows, x=x, y=y + 30, w=CELL_W - 40, h=150, value_label="% id")
    caption = f"Sequence identity of top BLAST hits (EBI/NCBI) against the search database. {len(hits)} hits returned."
    return [panel_header("A", "Top hits — sequence identity", x, y), body,
            panel_caption(caption, x + 4, y + 190, CELL_W - 20)]


def _domains_panel(domains: dict, index: int) -> list[str]:
    x, y = panel_xy(index)
    body = domain_blocks_panel(
        domains.get("domains") or [],
        seq_len=domains.get("sequence_length") or 0,
        x=x, y=y + 30, w=CELL_W - 40, h=150,
    )
    caption = f"Domain architecture from InterPro member signatures ({len(domains.get('domains') or [])} hits)."
    return [panel_header("B", "Domain architecture (InterPro)", x, y), body,
            panel_caption(caption, x + 4, y + 190, CELL_W - 20)]


def _msa_panel(msa: dict, index: int) -> list[str]:
    x, y = panel_xy(index)
    lines = [
        f"Sequences aligned: {msa.get('sequence_count', 0)}",
        f"Aligner: {msa.get('method', 'n/a')}",
        f"Mode: {msa.get('alignment_mode', 'global')}",
    ]
    if msa.get("pairwise"):
        lines.append("Pairwise refinement: enabled")
    body = text_lines_panel(lines, x=x + 10, y=y + 30, w=CELL_W - 40, h=120, size=12, max_lines=8)
    caption = "Multiple sequence alignment summary produced by the MSA stage (EBI ClustalO/MAFFT)."
    return [panel_header("C", "Multiple sequence alignment", x, y), body,
            panel_caption(caption, x + 4, y + 190, CELL_W - 20)]


def _phylo_panel(phylo: dict, index: int) -> list[str]:
    x, y = panel_xy(index)
    newick = phylo.get("phylotree_newick") or ""
    lines = wrap_text(newick[:300], 54)[:8] if newick else ["No guide tree recorded."]
    body = text_lines_panel(lines, x=x + 10, y=y + 30, w=CELL_W - 40, h=150, size=9, max_lines=8)
    caption = "Newick guide tree from the EBI MSA stage; rendered topology-only."
    return [panel_header("D", "Phylogenetic guide tree (Newick)", x, y), body,
            panel_caption(caption, x + 4, y + 190, CELL_W - 20)]


def _uniprot_panel(uniprot: dict, index: int) -> list[str]:
    x, y = panel_xy(index)
    lines = [
        f"Accession: {uniprot.get('accession', 'n/a')}",
        f"Full name: {uniprot.get('full_name', 'n/a')}",
        f"Organism: {uniprot.get('organism', 'n/a')}",
        f"Gene: {', '.join(uniprot.get('gene_names') or []) or 'n/a'}",
    ]
    body = text_lines_panel(lines, x=x + 10, y=y + 30, w=CELL_W - 40, h=120, size=12, max_lines=8)
    caption = "Retrieved UniProtKB entry for the query's top hit."
    return [panel_header("E", "UniProt annotation", x, y), body,
            panel_caption(caption, x + 4, y + 190, CELL_W - 20)]


def _interpret_panel(steps: dict, index: int) -> list[str]:
    x, y = panel_xy(index)
    text = ""
    interp = steps.get("interpret") or {}
    if isinstance(interp, dict):
        text = interp.get("interpretation") or interp.get("text") or ""
    elif isinstance(interp, str):
        text = interp
    if not text and steps.get("final_report"):
        text = steps["final_report"]
    lines = wrap_text(str(text), 54)[:9] if text else ["No AI interpretation recorded."]
    body = text_lines_panel(lines, x=x + 10, y=y + 30, w=CELL_W - 40, h=150, size=9, max_lines=9)
    caption = "AI interpretation with evidence provenance; unsupported claims are flagged."
    return [panel_header("F", "AI interpretation", x, y), body,
            panel_caption(caption, x + 4, y + 190, CELL_W - 20)]


def build_experiment_figure(context: dict | None, job_id: str = "unknown") -> str:
    """Compose one publication figure from a job's stored result context."""
    ctx = context or {}
    panels: list[str] = []

    panels += _blast_panel(ctx.get("blast") or {}, 0)
    panels += _domains_panel(ctx.get("domains") or {}, 1)
    panels += _msa_panel(ctx.get("msa") or {}, 2)
    panels += _phylo_panel(ctx.get("phylo") or {}, 3)
    panels += _uniprot_panel(ctx.get("uniprot") or {}, 4)
    panels += _interpret_panel(ctx, 5)

    svg = [svg_canvas(1200, 800)]
    svg.append(f'<rect x="0" y="0" width="1200" height="800" fill="#ffffff"/>')
    svg.append(title_block(f"BioNexus experiment analysis — {esc(job_id)}", 40, 30))
    svg.append(
        '<text x="40" y="50" font-size="10" fill="#6b7280">'
        'Panels: A top hits · B domain architecture · C alignment · D guide tree · E UniProt · F interpretation</text>'
    )
    svg.extend(panels)
    svg.append(footer_block("created on demand from the experiment record", CITATIONS, 40, 760))
    svg.append(svg_close())
    return "".join(svg)