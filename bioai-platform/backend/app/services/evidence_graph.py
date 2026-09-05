"""AI Evidence Engine (BioNexus 2.0, Component 9).

Every reported biological statement becomes a claim node that links back to the
computation and database release that supports it:

    Claim -> Evidence -> Tool -> Database -> Version -> Citation -> Confidence

Unsupported sentences are not silently carried: they are flagged `rejected` so
the reader sees exactly what the AI could not back up (honest-AI invariant
shared with the interpret engine).

This module builds the graph from a job's stored result context. The engine
(app/engines/evidence_engine.py) validates the graph under the engine contract.
"""

from __future__ import annotations

import re
from typing import Any

#: Static tool/database identity per result section.
SECTION_META: dict[str, dict[str, str]] = {
    "blast": {"tool": "BLAST+", "database": "EBI/NCBI", "version": "blast 2.14+"},
    "uniprot": {"tool": "UniProt API", "database": "UniProtKB", "version": "UniProt release 2025_05"},
    "msa": {"tool": "EBI MSA", "database": "SWISS-PROT homologs", "version": "Clustal Omega 1.2.4"},
    "phylo": {"tool": "Guide tree", "database": "EBI MSA", "version": "Clustal Omega 1.2.4"},
    "domains": {"tool": "InterPro", "database": "InterPro", "version": "InterPro release 108"},
    "pathway_enrichment": {"tool": "Reactome", "database": "Reactome", "version": "Reactome 2025"},
    "alphafold": {"tool": "AlphaFold DB", "database": "AlphaFold", "version": "v4"},
    "interpret": {"tool": "AI interpreter", "database": "synthesis", "version": "n/a"},
}

#: Engine citations that back each section's evidence.
SECTION_CITATIONS: dict[str, str] = {
    "blast": "Camacho C, et al. BLAST+. BMC Bioinformatics 10:421, 2009.",
    "uniprot": "UniProt Consortium. Nucleic Acids Res 51:D523-D531, 2023.",
    "msa": "Madeira F, et al. EMBL-EBI services 2022. Nucleic Acids Res 50:W276-W279, 2022.",
    "phylo": "Felsenstein J. PHYLIP. Cladistics 5:164-166, 1989.",
    "domains": "Paysan-Lafosse T, et al. InterPro in 2022. Nucleic Acids Res 51:D418-D427, 2023.",
    "pathway_enrichment": "Gillespie M, et al. Reactome 2022. Nucleic Acids Res 50:D687-D692, 2022.",
    "alphafold": "Jumper J, et al. Nature 596:583-589, 2021; Varadi M, et al. Nucleic Acids Res 52:D368, 2024.",
    "interpret": "BioNexus AI interpretation with evidence provenance.",
}

CONFIDENCE_TIERS = ("high", "medium", "low")


def sentence_split(text: str) -> list[str]:
    """Split free text into sentences (keep short; avoids acronym-wrecking)."""
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[.;!?])\s+", text)]
    return [p for p in parts if len(p) > 8]


def keyword_vocab(context: dict) -> dict[str, list[str]]:
    """Keyword per section: accessions, gene names, names, species, signifiers."""
    vocab: dict[str, list[str]] = {}

    blast = context.get("blast") or {}
    if blast:
        words = []
        top = blast.get("top_hit") or {}
        if top.get("accession"):
            words.append(str(top["accession"]))
        if top.get("description"):
            words += str(top["description"]).replace("-", " ").split()
        for h in (blast.get("hits") or [])[:5]:
            if h.get("accession"):
                words.append(str(h["accession"]))
        words += [str(blast.get("database") or ""), str(blast.get("program") or "")]
        vocab["blast"] = [w for w in words if len(w) >= 3]

    uniprot = context.get("uniprot") or {}
    if uniprot:
        words = [str(uniprot.get("accession") or "")]
        words += f"{uniprot.get('full_name') or ''} {uniprot.get('organism') or ''}".split()
        words += [g for g in (uniprot.get("gene_names") or [])]
        vocab["uniprot"] = [w for w in words if len(w) >= 3]

    msa = context.get("msa") or {}
    if msa:
        vocab["msa"] = ["alignment", str(msa.get("method") or ""), str(msa.get("alignment_mode") or "")]

    phylo = context.get("phylo") or {}
    if phylo:
        vocab["phylo"] = ["phylogen", "tree", "newick"]

    domains = context.get("domains") or {}
    if domains:
        words = [str(d.get("name") or "") for d in (domains.get("domains") or [])]
        words += [str(d.get("accession") or "") for d in (domains.get("domains") or [])][:10]
        words += ["domain", "interpro", "pfam"]
        vocab["domains"] = [w for w in words if len(w) >= 3]

    pathway = context.get("pathway_enrichment") or {}
    if pathway:
        words = [str(p.get("name") or "") for p in (pathway.get("pathways") or [])][:8]
        words += [str(p.get("stId") or "") for p in (pathway.get("pathways") or [])][:8]
        words += ["pathway", "enrichment", "reactome"]
        vocab["pathway_enrichment"] = [w for w in words if len(w) >= 3]

    alphafold = context.get("alphafold") or {}
    if alphafold:
        words = ["alphafold", "structure", str(alphafold.get("pdb_id") or "")]
        words += [str(alphafold.get("uniprot_accession") or "")]
        vocab["alphafold"] = [w for w in words if len(w) >= 3]

    return vocab


def _source_nodes(context: dict, sources_present: list[str]) -> list[dict]:
    nodes: list[dict] = []
    for section in sources_present:
        meta = SECTION_META.get(section, {})
        nodes.append({
            "id": section,
            "tool": meta.get("tool", section),
            "database": meta.get("database", ""),
            "version": meta.get("version", ""),
            "retrieved_at": "recorded",
            "citation": SECTION_CITATIONS.get(section, ""),
        })
    return nodes


def _link_claims(text: str, vocab: dict[str, list[str]], present: list[str]) -> list[dict]:
    claims: list[dict] = []
    lowered = text.lower()
    for i, sentence in enumerate(sentence_split(text)):
        evidence = []
        s_low = sentence.lower()
        for section in present:
            if any(kw.lower() in s_low for kw in vocab.get(section, []) if kw):
                evidence.append(section)
        supported = bool(evidence)
        confidence = "low"
        if supported:
            confidence = "high" if len(evidence) >= 2 else "medium"
        claims.append({
            "id": f"claim-{i + 1}",
            "text": sentence,
            "confidence": confidence,
            "evidence": evidence,
            "rejected": not supported,
        })
    return claims


def assemble_evidence(context: dict | None) -> dict:
    """Build the evidence graph for a job's stored context.

    Sections present in context become source nodes. Sentences of the AI
    interpretation become claim nodes linked to the sources whose keywords
    appear in the sentence; sentences with no linkable support are marked
    rejected (honest-AI).
    """
    ctx = context or {}
    present = [s for s in SECTION_META if ctx.get(s)]
    sources = _source_nodes(ctx, present)

    interp = ctx.get("interpret")
    text = ""
    if isinstance(interp, dict):
        text = interp.get("interpretation") or ""
    elif isinstance(interp, str):
        text = interp
    if not text:
        text = ctx.get("final_report") or ""

    vocabulary = keyword_vocab(ctx)
    claims = _link_claims(str(text), vocabulary, present)
    if not claims:
        claims = [{"id": "claim-0", "text": (str(text)[:200] or "No AI interpretation recorded."),
                   "confidence": "low", "evidence": [], "rejected": True}]

    edges = []
    for claim in claims:
        for sid in claim.get("evidence", []):
            edges.append({"from": sid, "to": claim["id"]})

    return {"sources": sources, "claims": claims, "edges": edges}