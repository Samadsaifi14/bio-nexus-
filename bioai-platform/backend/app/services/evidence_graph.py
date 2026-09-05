"""Evidence graph assembly for BioNexus audited AI.

Graph shape:
    claim -> source/computation -> tool -> database -> version -> timestamp

Every claim is assigned one of the project evidence classes. Unsupported claims
remain visible but are marked rejected; they are never silently promoted into a
scientific result. Numeric claims are admitted only when the same numeric token
appears in their linked evidence payload (or a future explicit derived-compute
node supplies it).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.services.evidence_policy import classify_claim, classify_source

SECTION_META: dict[str, dict[str, str]] = {
    "blast": {"tool": "BLAST", "database": "configured BLAST database"},
    "uniprot": {"tool": "UniProt API", "database": "UniProtKB"},
    "msa": {"tool": "MSA engine", "database": "input/homolog sequences"},
    "phylo": {"tool": "phylogenetics engine", "database": "aligned sequences"},
    "domains": {"tool": "InterPro/Pfam annotation", "database": "InterPro/Pfam"},
    "pathway_enrichment": {"tool": "pathway enrichment", "database": "Reactome/GO/KEGG"},
    "alphafold": {"tool": "AlphaFold retrieval", "database": "AlphaFold DB"},
    "pdb": {"tool": "PDB retrieval", "database": "RCSB PDB"},
    "docking": {"tool": "docking engine", "database": "input receptor/ligand"},
    "md": {"tool": "molecular dynamics engine", "database": "trajectory"},
    "ngs": {"tool": "NGS workflow", "database": "reference genome/annotation"},
    "stats": {"tool": "BioNexus statistics engine", "database": "recorded result data"},
    "primers": {"tool": "primer design engine", "database": "target/reference sequence"},
    "sequence": {"tool": "sequence analysis engine", "database": "input sequence"},
    "interpret": {"tool": "Evidence-Aware AI", "database": "recorded BioNexus evidence"},
}

SECTION_CITATIONS: dict[str, str] = {
    "blast": "Camacho C, et al. BLAST+. BMC Bioinformatics 10:421, 2009.",
    "uniprot": "UniProt Consortium. UniProt: the Universal Protein Knowledgebase.",
    "msa": "Madeira F, et al. Search and sequence analysis tools services at EMBL-EBI.",
    "domains": "Paysan-Lafosse T, et al. InterPro protein classification resource.",
    "pathway_enrichment": "Gillespie M, et al. Reactome pathway knowledgebase.",
    "alphafold": "Jumper J, et al. Highly accurate protein structure prediction with AlphaFold. Nature 2021.",
    "pdb": "Berman HM, et al. The Protein Data Bank. Nucleic Acids Res 2000.",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sentence_split(text: str) -> list[str]:
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[.;!?])\s+", text)]
    return [p for p in parts if len(p) > 8]


def _flatten_tokens(value: Any) -> list[str]:
    text = str(value or "")
    tokens = re.findall(r"[A-Za-z0-9_.:-]{3,}", text)
    # preserve stable ordering while avoiding huge vocabularies
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        low = token.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(token)
        if len(out) >= 80:
            break
    return out


def keyword_vocab(context: dict) -> dict[str, list[str]]:
    return {section: _flatten_tokens(payload) for section, payload in context.items() if payload and section != "interpret"}


def _version_from_payload(section: str, payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("database_version", "db_version", "release", "version", "tool_version"):
        value = payload.get(key)
        if value:
            return str(value)
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in ("database_version", "release", "version", "tool_version"):
            if metadata.get(key):
                return str(metadata[key])
    return None


def _timestamp_from_payload(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("retrieved_at", "timestamp", "created_at", "completed_at", "run_at"):
        if payload.get(key):
            return str(payload[key])
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in ("retrieved_at", "timestamp", "completed_at"):
            if metadata.get(key):
                return str(metadata[key])
    return None


def _source_nodes(context: dict, sources_present: list[str]) -> list[dict]:
    nodes: list[dict] = []
    for section in sources_present:
        payload = context.get(section)
        meta = SECTION_META.get(section, {"tool": section, "database": "recorded result"})
        node = {
            "id": section,
            "tool": meta.get("tool", section),
            "database": meta.get("database", "recorded result"),
            "version": _version_from_payload(section, payload),
            "retrieved_at": _timestamp_from_payload(payload),
            "recorded_at": _utc_now(),
            "evidence_class": classify_source(section, payload).value,
            "citation": SECTION_CITATIONS.get(section),
            "benchmark_refs": (payload.get("benchmark_refs") if isinstance(payload, dict) else None) or [],
        }
        nodes.append(node)
    return nodes


def _link_claims(text: str, vocab: dict[str, list[str]], present: list[str], context: dict) -> list[dict]:
    claims: list[dict] = []
    for i, sentence in enumerate(sentence_split(text)):
        s_low = sentence.lower()
        evidence: list[str] = []
        for section in present:
            if any(token.lower() in s_low for token in vocab.get(section, []) if token):
                evidence.append(section)
        policy = classify_claim(sentence=sentence, evidence_sections=evidence, context=context)
        confidence = "none"
        if policy["admitted"]:
            confidence = "high" if len(evidence) >= 2 else "medium"
        claims.append({
            "id": f"claim-{i + 1}",
            "text": sentence,
            "confidence": confidence,
            "evidence": evidence,
            "evidence_refs": evidence,
            "evidence_class": policy["evidence_class"],
            "numeric_claims": policy["numeric_claims"],
            "unsupported_numeric_claims": policy["unsupported_numeric_claims"],
            "rejected": not policy["admitted"],
            "rejection_reason": None if policy["admitted"] else policy["reason"],
        })
    return claims


def assemble_evidence(context: dict | None) -> dict:
    ctx = context or {}
    present = [s for s in ctx if s != "interpret" and ctx.get(s)]
    sources = _source_nodes(ctx, present)

    interp = ctx.get("interpret")
    text = ""
    if isinstance(interp, dict):
        text = interp.get("interpretation") or interp.get("text") or ""
    elif isinstance(interp, str):
        text = interp
    if not text:
        text = str(ctx.get("final_report") or "")

    claims = _link_claims(text, keyword_vocab(ctx), present, ctx)
    if not claims:
        claims = [{
            "id": "claim-0",
            "text": str(text)[:200] or "No AI interpretation recorded.",
            "confidence": "none",
            "evidence": [],
            "evidence_refs": [],
            "evidence_class": "unsupported/insufficient evidence",
            "numeric_claims": [],
            "unsupported_numeric_claims": [],
            "rejected": True,
            "rejection_reason": "no auditable interpretation was recorded",
        }]

    edges = [{"from": sid, "to": claim["id"], "relation": "supports"}
             for claim in claims for sid in claim.get("evidence", [])]
    rejected = sum(1 for claim in claims if claim.get("rejected"))
    return {
        "schema": "bionexus-evidence-graph/v2",
        "generated_at_utc": _utc_now(),
        "sources": sources,
        "claims": claims,
        "edges": edges,
        "summary": {
            "source_count": len(sources),
            "claim_count": len(claims),
            "rejected_claim_count": rejected,
            "unsupported_claim_rate": (rejected / len(claims)) if claims else 0.0,
        },
    }
