"""Publication Engine (BioNexus 2.0, Component 10).

Generates a manuscript draft from a recorded experiment: Methods, Results,
Figures (with captions), Supplementary data, Statistics, References, Data
Availability, Code Availability and Declarations, formatted for common
journals. Every statement in Results traces to the stored result context and
the engine citations, so the paper is an artifact of the run — not manual copy
(also the foundation of Component 18 and the E3 publication-artifact generator).
"""

from __future__ import annotations

from typing import Any

from app.services.evidence_graph import SECTION_CITATIONS

JOURNAL_TEMPLATES = {
    "nature": {
        "label": "Nature",
        "style": "Methods before Results, numbered references, 200-word summary",
        "sections": ["title", "abstract", "introduction", "methods", "results", "figures", "data_availability", "code_availability", "references", "declarations"],
    },
    "bmc": {
        "label": "BMC Bioinformatics",
        "style": "Declarations block, structured abstract",
        "sections": ["title", "abstract", "background", "methods", "results", "conclusions", "figures", "declarations", "references", "data_availability", "code_availability"],
    },
    "nar": {
        "label": "Nucleic Acids Research",
        "style": "Materials and Methods, Results, Discussion, Web server notes",
        "sections": ["title", "abstract", "introduction", "materials_methods", "results", "discussion", "figures", "references", "data_availability"],
    },
    "ieee": {
        "label": "IEEE/ACM TCBB",
        "style": "Abstract, Index Terms, numbered sections, references",
        "sections": ["title", "abstract", "index_terms", "introduction", "methods", "results", "conclusion", "references"],
    },
}


def _pretty(value: Any, default: str = "n/a") -> str:
    if value is None:
        return default
    return str(value)


def _cite(toolkey: str, seen: set[str]) -> str:
    cite = SECTION_CITATIONS.get(toolkey)
    if cite and cite not in seen:
        seen.add(cite)
        return cite
    return ""


def section_snapshot(context: dict) -> dict:
    """Compact, reviewable statistics per result section (used in Results)."""
    blast = context.get("blast") or {}
    uniprot = context.get("uniprot") or {}
    msa = context.get("msa") or {}
    domains = context.get("domains") or {}
    pathway = context.get("pathway_enrichment") or {}
    alphafold = context.get("alphafold") or {}

    snap: dict[str, Any] = {
        "toplevel": {
            "title": _pretty((blast.get("top_hit") or {}).get("description") or context.get("query", {}).get("accession") or (context.get("sequence") or "")[:60]),
            "n_sections": sum(1 for s in SECTION_CITATIONS if context.get(s)),
        },
        "blast": {
            "hit_count": blast.get("count", 0),
            "top_hit": _pretty((blast.get("top_hit") or {}).get("accession")),
            "identity_pct": blast.get("top_hit", {}).get("identity_pct") if blast.get("top_hit") else None,
            "evalue": blast.get("top_hit", {}).get("evalue") if blast.get("top_hit") else None,
            "database": _pretty(blast.get("database")),
            "program": _pretty(blast.get("program")),
        },
        "uniprot": {
            "accession": _pretty(uniprot.get("accession")),
            "gene": ", ".join(uniprot.get("gene_names") or []),
            "organism": _pretty(uniprot.get("organism")),
            "full_name": _pretty(uniprot.get("full_name")),
        },
        "domains": {
            "count": len(domains.get("domains") or []),
            "top_accession": (domains.get("domains") or [{}])[0].get("accession") if domains.get("domains") else None,
        },
        "msa": {"sequence_count": msa.get("sequence_count", 0), "method": _pretty(msa.get("method"))},
        "pathway": {"count": len(pathway.get("pathways") or []), "top": (pathway.get("pathways") or [{}])[0].get("name") if pathway.get("pathways") else None},
        "alphafold": {
            "structure_available": bool(alphafold.get("structure_available")),
            "confidence": alphafold.get("confidence"),
            "pdb_url": _pretty(alphafold.get("pdb_url")),
        },
    }
    return snap


def render_paper(context: dict | None, job_id: str = "unknown") -> dict:
    """Assemble the manuscript dictionary from a job's result context."""
    ctx = context or {}
    snap = section_snapshot(ctx)

    seen: set[str] = set()
    references: list[str] = []
    for key in ("blast", "uniprot", "msa", "phylo", "domains", "pathway_enrichment", "alphafold"):
        cite = _cite(key, seen)
        if cite:
            references.append(cite)

    title = snap["toplevel"]["title"] or f"BioNexus experiment {job_id}"
    snap["toplevel"]["title"] = title

    figures = []
    for idx, (label, fig_title) in enumerate(
        (("A", "Top hits — sequence identity"), ("B", "Domain architecture (InterPro)"),
         ("C", "Multiple sequence alignment"), ("D", "Phylogenetic guide tree (Newick)"),
         ("E", "UniProt annotation"), ("F", "AI interpretation"))
    ):
        figures.append({"figure": f"Figure {idx + 1}", "panel": label, "caption": fig_title,
                        "source": f"/api/figures/{job_id}"})

    methods = _render_methods(ctx)
    results = _render_results(snap)

    return {
        "title": title,
        "experiment_id": job_id,
        "abstract": (
            f"A parallelized bioinformatics analysis was run on the query sequence "
            f"({snap['blast']['top_hit']}) producing hits, annotations, alignments "
            f"and an evidence-backed AI interpretation. Results are reproducible from "
            f"the recorded experiment via its immutable experiment fingerprint."
        ),
        "methods": methods,
        "results": results,
        "statistics": snap,
        "figures": figures,
        "supplementary": [
            {"name": "hit_table", "format": "csv", "href": f"/api/experiments/{job_id}/context/blast", "source": "BLAST+ output"},
            {"name": "domain_annotation", "format": "json", "href": f"/api/experiments/{job_id}/context/domains", "source": "InterPro"},
            {"name": "msa_alignment", "format": "fasta", "href": f"/api/experiments/{job_id}/context/msa", "source": "EBI MSA"},
        ],
        "data_availability": (
            "All analyses, provenance graphs and benchmark runs are stored in the BioNexus "
            "scientific data layer and are exportable from the experiment record."
        ),
        "code_availability": (
            "The BioNexus engine registry is versioned in git; each engine declares its "
            "tool, database and version. See /api/engines and the git commit recorded on "
            "the experiment fingerprint."
        ),
        "declarations": {"conflict_of_interest": "The authors declare no competing interests.",
                         "funding": "BioNexus research platform.", "ethics": "No human subjects; public reference data only."},
        "references": references,
        "journal_formats": {name: spec["label"] for name, spec in JOURNAL_TEMPLATES.items()},
    }


def _render_methods(ctx: dict) -> str:
    lines = []
    used = [k for k in ("blast", "uniprot", "msa", "phylo", "domains", "pathway_enrichment", "alphafold", "interpret") if ctx.get(k)]
    lines.append("The query was processed through the parallelized BioNexus pipeline. Performed stages: " +
                 ", ".join(used) + ".")
    blast = ctx.get("blast") or {}
    if blast.get("program"):
        lines.append(f"Sequence homology was assessed with {blast.get('program')} against "
                     f"{blast.get('database')} (EBI/NCBI; {blast.get('count', 0)} hits retrieved).")
    uniprot = ctx.get("uniprot") or {}
    if uniprot.get("accession"):
        lines.append(f"Top-hit annotation was retrieved from UniProtKB/Swiss-Prot "
                     f"(accession {uniprot['accession']}).")
    interp = ctx.get("interpret") or {}
    if isinstance(interp, dict) and interp.get("interpretation"):
        lines.append("A final AI interpretation was generated with evidence provenance: each "
                     "statement is linked to its supporting computation or explicitly rejected.")
    return "\n".join(lines)


def _render_results(snap: dict) -> list[str]:
    rows = []
    b = snap["blast"]
    rows.append(f"BLAST identified {b['hit_count']} homologs; the top hit was {b['top_hit']} "
                f"(identity {b['identity_pct']}%).")
    u = snap["uniprot"]
    rows.append(f"The query maps to UniProtKB entry {u['accession']} ({u['full_name']}; "
                f"gene {u['gene'] or 'unknown'}, {u['organism']}).")
    d = snap["domains"]
    rows.append(f"InterPro assigned {d['count']} domain signatures"
                + (f" (lead: {d['top_accession']})." if d.get("top_accession") else "."))
    m = snap["msa"]
    if m["sequence_count"]:
        rows.append(f"Multiple sequence alignment covered {m['sequence_count']} sequences "
                    f"(aligner: {m['method']}).")
    p = snap["pathway"]
    if p.get("top"):
        rows.append(f"Reactome enrichment returned {p['count']} pathways (lead: {p['top']}).")
    a = snap["alphafold"]
    rows.append(f"Structural coverage: AlphaFold {'available' if a['structure_available'] else 'unavailable'} "
                f"(confidence {a['confidence'] or 'n/a'}).")
    return rows


def render_markdown(paper: dict, journal: str = "bmc") -> str:
    """Flat, journal-shaped Markdown draft of a paper dictionary."""
    sections = [paper["title"], "\n## Abstract", paper["abstract"], "\n## Background" if journal == "bmc" else "\n## Introduction"]
    sections += ["\n## Methods", paper["methods"]]
    sections += ["\n## Results"] + [f"- {r}" for r in paper["results"]]
    sections += ["\n## Figures"]
    sections += [f"- {f['figure']}: {f['panel']} {f['caption']} ({f['source']})" for f in paper["figures"]]
    sections += ["\n## Data availability", paper["data_availability"],
                 "\n## Code availability", paper["code_availability"],
                 "\n## Declarations"]
    sections += [f"- {k}: {v}" for k, v in paper["declarations"].items()]
    sections += ["\n## References"] + [f"{i + 1}. {r}" for i, r in enumerate(paper["references"])]
    return "\n".join(sections) + "\n"