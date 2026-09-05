"""Reviewer-traceable evidence graph for BioNexus audited AI.

Canonical reviewer path:
    claim -> evidence -> algorithm -> database -> version -> parameters
          -> confidence -> benchmark

The graph is deliberately conservative. Missing provenance stays explicit as
``unknown``/``not recorded`` nodes; it is never synthesized. The legacy
``sources`` and claim ``evidence_refs`` fields are retained for existing API
clients while ``nodes``/``edges`` provide the publishable typed graph.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from app.services.evidence_policy import classify_claim, classify_source

SECTION_META: dict[str, dict[str, str]] = {
    "blast": {"tool": "BLAST", "algorithm": "local sequence similarity search", "database": "configured BLAST database"},
    "uniprot": {"tool": "UniProt API", "algorithm": "reference record retrieval", "database": "UniProtKB"},
    "msa": {"tool": "MSA engine", "algorithm": "multiple sequence alignment", "database": "input/homolog sequences"},
    "phylo": {"tool": "phylogenetics engine", "algorithm": "phylogenetic inference/post-processing", "database": "aligned sequences"},
    "domains": {"tool": "InterPro/Pfam annotation", "algorithm": "domain/family annotation", "database": "InterPro/Pfam"},
    "pathway_enrichment": {"tool": "pathway enrichment", "algorithm": "gene-set/pathway enrichment", "database": "Reactome/GO/KEGG"},
    "alphafold": {"tool": "AlphaFold retrieval", "algorithm": "predicted-structure retrieval", "database": "AlphaFold DB"},
    "pdb": {"tool": "PDB retrieval", "algorithm": "experimental-structure retrieval", "database": "RCSB PDB"},
    "docking": {"tool": "docking engine", "algorithm": "molecular docking", "database": "input receptor/ligand"},
    "md": {"tool": "molecular dynamics engine", "algorithm": "molecular dynamics simulation/analysis", "database": "trajectory"},
    "ngs": {"tool": "NGS workflow", "algorithm": "sequencing analysis workflow", "database": "reference genome/annotation"},
    "stats": {"tool": "BioNexus statistics engine", "algorithm": "statistical analysis", "database": "recorded result data"},
    "primers": {"tool": "primer design engine", "algorithm": "primer design/screening", "database": "target/reference sequence"},
    "sequence": {"tool": "sequence analysis engine", "algorithm": "deterministic sequence analysis", "database": "input sequence"},
    "interpret": {"tool": "Evidence-Aware AI", "algorithm": "evidence-constrained interpretation", "database": "recorded BioNexus evidence"},
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

PARAMETER_KEYS = (
    "parameters", "params", "settings", "configuration", "config", "options",
    "thresholds", "seed", "random_seed", "cutoff", "evalue", "identity",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]}"


def sentence_split(text: str) -> list[str]:
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[.;!?])\s+", text)]
    return [p for p in parts if len(p) > 8]


def _flatten_tokens(value: Any) -> list[str]:
    text = str(value or "")
    tokens = re.findall(r"[A-Za-z0-9_.:-]{3,}", text)
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
    for key in ("database_version", "db_version", "release", "version", "tool_version", "software_version"):
        value = payload.get(key)
        if value:
            return str(value)
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in ("database_version", "release", "version", "tool_version", "software_version"):
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


def _parameters_from_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    found: dict[str, Any] = {}
    for key in PARAMETER_KEYS:
        if key in payload and payload[key] not in (None, "", [], {}):
            found[key] = payload[key]
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in PARAMETER_KEYS:
            if key in metadata and metadata[key] not in (None, "", [], {}):
                found[f"metadata.{key}"] = metadata[key]
    return found


def _benchmark_refs(payload: Any) -> list[Any]:
    if not isinstance(payload, dict):
        return []
    refs = payload.get("benchmark_refs") or payload.get("benchmarks") or []
    if isinstance(refs, (str, dict)):
        refs = [refs]
    return list(refs) if isinstance(refs, list) else []


def _payload_digest(payload: Any) -> str:
    try:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    except TypeError:
        body = str(payload)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _source_nodes(context: dict, sources_present: list[str]) -> list[dict]:
    nodes: list[dict] = []
    for section in sources_present:
        payload = context.get(section)
        meta = SECTION_META.get(section, {"tool": section, "algorithm": section, "database": "recorded result"})
        nodes.append({
            "id": section,
            "tool": meta.get("tool", section),
            "algorithm": meta.get("algorithm", meta.get("tool", section)),
            "database": meta.get("database", "recorded result"),
            "version": _version_from_payload(section, payload),
            "parameters": _parameters_from_payload(payload),
            "retrieved_at": _timestamp_from_payload(payload),
            "recorded_at": _utc_now(),
            "evidence_class": classify_source(section, payload).value,
            "citation": SECTION_CITATIONS.get(section),
            "benchmark_refs": _benchmark_refs(payload),
            "payload_sha256": _payload_digest(payload),
        })
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


def _typed_graph(claims: list[dict], sources: list[dict]) -> tuple[list[dict], list[dict]]:
    """Expand compatibility source records into explicit reviewer-traversable nodes."""
    nodes: list[dict] = []
    edges: list[dict] = []
    source_by_id = {s["id"]: s for s in sources}

    for claim in claims:
        cid = claim["id"]
        conf_id = _stable_id("confidence", cid, claim.get("confidence"))
        nodes.append({"id": cid, "type": "claim", "label": claim.get("text"), "data": claim})
        nodes.append({
            "id": conf_id,
            "type": "confidence",
            "label": claim.get("confidence", "none"),
            "data": {"level": claim.get("confidence", "none"), "rejected": bool(claim.get("rejected"))},
        })
        edges.append({"from": cid, "to": conf_id, "relation": "has_confidence"})

        for source_id in claim.get("evidence_refs", []):
            source = source_by_id.get(source_id)
            if not source:
                continue
            evid_id = _stable_id("evidence", cid, source_id)
            alg_id = _stable_id("algorithm", source_id, source.get("algorithm"))
            db_id = _stable_id("database", source_id, source.get("database"))
            ver_id = _stable_id("version", source_id, source.get("version") or "not-recorded")
            par_id = _stable_id("parameters", source_id, json.dumps(source.get("parameters") or {}, sort_keys=True, default=str))

            nodes.extend([
                {"id": evid_id, "type": "evidence", "label": source_id, "data": {
                    "section": source_id,
                    "evidence_class": source.get("evidence_class"),
                    "citation": source.get("citation"),
                    "payload_sha256": source.get("payload_sha256"),
                    "retrieved_at": source.get("retrieved_at"),
                }},
                {"id": alg_id, "type": "algorithm", "label": source.get("algorithm") or source.get("tool") or "not recorded", "data": {"tool": source.get("tool")}},
                {"id": db_id, "type": "database", "label": source.get("database") or "not recorded", "data": {}},
                {"id": ver_id, "type": "version", "label": source.get("version") or "not recorded", "data": {}},
                {"id": par_id, "type": "parameters", "label": "recorded parameters" if source.get("parameters") else "parameters not recorded", "data": source.get("parameters") or {}},
            ])
            edges.extend([
                {"from": cid, "to": evid_id, "relation": "supported_by"},
                {"from": evid_id, "to": alg_id, "relation": "generated_by"},
                {"from": alg_id, "to": db_id, "relation": "uses_database"},
                {"from": db_id, "to": ver_id, "relation": "has_version"},
                {"from": ver_id, "to": par_id, "relation": "executed_with"},
                {"from": par_id, "to": conf_id, "relation": "contributes_to_confidence"},
            ])

            refs = source.get("benchmark_refs") or []
            if not refs:
                bench_id = _stable_id("benchmark", source_id, "not-recorded")
                nodes.append({"id": bench_id, "type": "benchmark", "label": "benchmark not recorded", "data": {"status": "not_recorded"}})
                edges.append({"from": conf_id, "to": bench_id, "relation": "evaluated_by"})
            else:
                for ref in refs:
                    bench_id = _stable_id("benchmark", source_id, ref)
                    nodes.append({"id": bench_id, "type": "benchmark", "label": str(ref), "data": {"reference": ref}})
                    edges.append({"from": conf_id, "to": bench_id, "relation": "evaluated_by"})

    # Stable deduplication because one source can support multiple claims.
    dedup_nodes: dict[str, dict] = {n["id"]: n for n in nodes}
    dedup_edges: dict[tuple[str, str, str], dict] = {(e["from"], e["to"], e["relation"]): e for e in edges}
    return list(dedup_nodes.values()), list(dedup_edges.values())


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

    nodes, typed_edges = _typed_graph(claims, sources)
    compatibility_edges = [
        {"from": sid, "to": claim["id"], "relation": "supports"}
        for claim in claims for sid in claim.get("evidence", [])
    ]
    rejected = sum(1 for claim in claims if claim.get("rejected"))
    node_type_counts: dict[str, int] = {}
    for node in nodes:
        node_type_counts[node["type"]] = node_type_counts.get(node["type"], 0) + 1

    return {
        "schema": "bionexus-evidence-graph/v3",
        "generated_at_utc": _utc_now(),
        "reviewer_path": ["claim", "evidence", "algorithm", "database", "version", "parameters", "confidence", "benchmark"],
        "nodes": nodes,
        "edges": typed_edges,
        "sources": sources,
        "claims": claims,
        "compatibility_edges": compatibility_edges,
        "summary": {
            "source_count": len(sources),
            "claim_count": len(claims),
            "node_count": len(nodes),
            "edge_count": len(typed_edges),
            "node_type_counts": node_type_counts,
            "rejected_claim_count": rejected,
            "unsupported_claim_rate": (rejected / len(claims)) if claims else 0.0,
        },
    }
