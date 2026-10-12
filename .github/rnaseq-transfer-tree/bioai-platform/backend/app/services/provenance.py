"""Milestone 1 — Provenance Graph.

Every pipeline result exposes a clickable trace:
    Sequence -> BLAST -> UniProt -> InterPro -> GO -> Reactome -> AI

Each recorded step is a node with its producing tool (+ version), the
reference database release it queried, the parameters it received, the node(s)
it consumed (deps), and compact evidence. Nothing is hidden: the same context
that drove the UI is persisted verbatim as `evidence`.

Like experiment.py, all writes are best-effort and never raise into the caller.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.services.supabase import get_supabase

logger = logging.getLogger(__name__)


def record_step(
    experiment_id: str,
    node_id: str,
    *,
    tool: str,
    database: str | None = None,
    tool_version: str | None = None,
    database_version: str | None = None,
    params: dict | None = None,
    deps: list[str] | None = None,
    input_ref: str | None = None,
    output_ref: str | None = None,
    evidence: dict | None = None,
    status: str = "complete",
) -> None:
    """Record a single provenance node for an experiment.

    node_id is the stable step key (e.g. 'blast', 'uniprot', 'interpro').
    deps lists other node_ids this node consumed, building the DAG.
    """
    if not experiment_id:
        return
    row = {
        "experiment_id": experiment_id,
        "node_id": node_id,
        "tool": tool,
        "tool_version": tool_version,
        "database": database,
        "database_version": database_version,
        "params": params or {},
        "deps": deps or [],
        "input_ref": input_ref,
        "output_ref": output_ref,
        "evidence": evidence or {},
        "status": status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        get_supabase().table("experiment_steps").upsert(row, on_conflict="experiment_id,node_id").execute()
    except Exception as e:
        logger.warning("Provenance record failed (%s): %s", node_id, e)


def trace_for_job(job_id: str, experiment_id: str | None) -> dict:
    """A clickable DAG: nodes + edges derived from each node's deps."""
    from app.services.experiment import _find_experiment, provenance_for_experiment

    steps = []
    exp_id = None
    if experiment_id:
        exp_id = experiment_id
    else:
        exp = _find_experiment(job_id)
        if not exp:
            return {"experiment_id": None, "nodes": [], "edges": []}
        exp_id = exp["experiment_id"]
    steps = provenance_for_experiment(exp_id)
    nodes = [{
        "id": s["node_id"],
        "tool": s.get("tool"),
        "database": s.get("database"),
        "database_version": s.get("database_version"),
        "params": s.get("params"),
        "evidence": s.get("evidence"),
        "input_ref": s.get("input_ref"),
        "output_ref": s.get("output_ref"),
        "status": s.get("status"),
        "completed_at": s.get("completed_at"),
    } for s in steps]
    edges = []
    ids = {n["id"] for n in nodes}
    for s in steps:
        for dep in (s.get("deps") or []):
            if dep in ids:
                edges.append({"from": dep, "to": s["node_id"]})
    return {"experiment_id": exp_id, "nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# Evidence extraction helpers — snap compact, reviewable facts from results.
# ---------------------------------------------------------------------------

def blast_evidence(result: dict) -> dict:
    return {
        "source": result.get("source"),
        "database": result.get("database"),
        "program": result.get("program"),
        "count": result.get("count", 0),
        "top_hit": result.get("top_hit", {}).get("accession"),
        "top_hit_description": result.get("top_hit", {}).get("description"),
        "query_length": result.get("query_length", 0),
    }


def uniprot_evidence(result: dict) -> dict:
    return {
        "accession": result.get("accession"),
        "organism": result.get("organism"),
        "gene_name": result.get("gene_name"),
        "resolved": result.get("resolved_uniprot", False),
        "pdb_ids": (result.get("pdb_ids") or [])[:3],
    }


def domains_evidence(result: dict) -> dict:
    doms = result.get("domains") or []
    return {
        "count": len(doms) if isinstance(doms, list) else 0,
        "first_accession": doms[0].get("accession") if isinstance(doms, list) and doms else None,
        "sources": sorted({d.get("source_db") for d in doms if isinstance(d, dict) and d.get("source_db")}),
    }


def pathway_evidence(result: dict) -> dict:
    pws = result.get("pathways") or []
    return {
        "count": len(pws) if isinstance(pws, list) else 0,
        "first_pathway": pws[0].get("name") if isinstance(pws, list) and pws else None,
        "first_st_id": pws[0].get("stId") if isinstance(pws, list) and pws else None,
    }


def msa_evidence(result: dict) -> dict:
    return {
        "tool": result.get("tool"), 
        "alignment_length": result.get("alignment_length", 0),
        "n_sequences": len(result.get("sequences") or []),
        "has_phylotree": bool(result.get("phylotree")),
    }


def predict_evidence(result: dict) -> dict:
    return {
        "model": result.get("model"),
        "structure_available": result.get("structure_available", False),
        "source": result.get("source"),
        "pdb_id": result.get("pdb_id"),
    }


# ---------------------------------------------------------------------------
# Pipeline-level provenance recorder — builds the DAG from the final context.
# ---------------------------------------------------------------------------

def record_pipeline_provenance(experiment_id: str, context: dict) -> None:
    """Record one provenance node per pipeline step found in the context.

    The DAG follows the pipeline's static dependency order:
        blast -> {uniprot, msa -> phylo} -> {domains, pathway_enrichment,
        alphafold} -> interpret
    Each node's evidence is a compact, reviewable snapshot of that step's
    result. Only steps actually present in the context are recorded.
    """
    if not experiment_id or not isinstance(context, dict):
        return

    blast = context.get("blast")
    if isinstance(blast, dict) and blast.get("top_hit"):
        record_step(
            experiment_id,
            "blast",
            tool="BLAST",
            database=blast.get("database"),
            params={"database": blast.get("database"), "program": blast.get("program")},
            deps=[],
            input_ref=context.get("sequence", "")[:80],
            evidence=blast_evidence(blast),
        )
    else:
        record_step(
            experiment_id, "blast", tool="BLAST",
            status="failed" if blast and isinstance(blast, dict) and blast.get("error") else "skipped",
            evidence=(blast_evidence(blast) if isinstance(blast, dict) else {}),
        )

    uniprot = context.get("uniprot")
    if isinstance(uniprot, dict) and uniprot.get("accession"):
        record_step(
            experiment_id, "uniprot", tool="UniProt",
            database="UniProtKB",
            deps=["blast"],
            input_ref=uniprot.get("accession"),
            evidence=uniprot_evidence(uniprot),
        )

    msa = context.get("msa")
    if isinstance(msa, dict) and msa.get("aln_fasta"):
        record_step(
            experiment_id, "msa", tool=msa.get("tool") or "MSA",
            deps=["blast"],
            evidence=msa_evidence(msa),
        )

    phylo = context.get("phylo")
    if isinstance(phylo, dict) and phylo.get("phylotree_newick"):
        record_step(
            experiment_id, "phylo", tool="Phylogeny",
            deps=["msa"],
            evidence={"has_newick": True},
        )

    domains = context.get("domains")
    if isinstance(domains, dict) and domains.get("domains"):
        record_step(
            experiment_id, "domains", tool="InterPro",
            database="InterPro",
            deps=["uniprot"],
            evidence=domains_evidence(domains),
        )

    pathway = context.get("pathway_enrichment")
    if isinstance(pathway, dict) and pathway.get("pathways"):
        record_step(
            experiment_id, "pathway_enrichment", tool="Reactome",
            database="Reactome",
            deps=["blast"],
            evidence=pathway_evidence(pathway),
        )

    alphafold = context.get("alphafold")
    if isinstance(alphafold, dict):
        record_step(
            experiment_id, "alphafold",
            tool="AlphaFold" if alphafold.get("structure_available") else "ESMFold",
            deps=["uniprot"],
            evidence=predict_evidence(alphafold),
        )

    interp = context.get("interpret")
    if isinstance(interp, dict) and interp.get("interpretation"):
        record_step(
            experiment_id, "interpret",
            tool=interp.get("model") or "AI interpreter",
            deps=["blast", "uniprot", "domains", "pathway_enrichment"],
            evidence={"character_length": len(str(interp.get("interpretation", "")))},
        )