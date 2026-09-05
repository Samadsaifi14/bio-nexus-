"""Reviewer-traceable evidence graph for BioNexus audited AI.

Canonical reviewer path:
claim -> evidence -> algorithm -> database -> version -> parameters -> confidence -> benchmark.

Legacy ``sources``, claim ``evidence_refs`` and source->claim ``edges`` are
preserved for existing clients. The richer chain is exposed as ``typed_edges``.
Missing provenance remains explicit and is never synthesized.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from app.services.evidence_policy import classify_claim, classify_source

SECTION_META = {
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

SECTION_CITATIONS = {
    "blast": "Camacho C, et al. BLAST+. BMC Bioinformatics 10:421, 2009.",
    "uniprot": "UniProt Consortium. UniProt: the Universal Protein Knowledgebase.",
    "msa": "Madeira F, et al. Search and sequence analysis tools services at EMBL-EBI.",
    "domains": "Paysan-Lafosse T, et al. InterPro protein classification resource.",
    "pathway_enrichment": "Gillespie M, et al. Reactome pathway knowledgebase.",
    "alphafold": "Jumper J, et al. Highly accurate protein structure prediction with AlphaFold. Nature 2021.",
    "pdb": "Berman HM, et al. The Protein Data Bank. Nucleic Acids Res 2000.",
}
PARAMETER_KEYS = ("parameters", "params", "settings", "configuration", "config", "options", "thresholds", "seed", "random_seed", "cutoff", "evalue", "identity")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def sentence_split(text: str) -> list[str]:
    if not text:
        return []
    return [p for p in (x.strip() for x in re.split(r"(?<=[.;!?])\s+", text)) if len(p) > 8]


def _flatten_tokens(value: Any) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9_.:-]{3,}", str(value or ""))
    seen, out = set(), []
    for token in tokens:
        low = token.lower()
        if low not in seen:
            seen.add(low); out.append(token)
        if len(out) >= 80:
            break
    return out


def keyword_vocab(context: dict) -> dict[str, list[str]]:
    return {section: _flatten_tokens(payload) for section, payload in context.items() if payload and section != "interpret"}


def _version(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("database_version", "db_version", "release", "version", "tool_version", "software_version"):
        if payload.get(key): return str(payload[key])
    meta = payload.get("metadata")
    if isinstance(meta, dict):
        for key in ("database_version", "release", "version", "tool_version", "software_version"):
            if meta.get(key): return str(meta[key])
    return None


def _timestamp(payload: Any) -> str | None:
    if not isinstance(payload, dict): return None
    for key in ("retrieved_at", "timestamp", "created_at", "completed_at", "run_at"):
        if payload.get(key): return str(payload[key])
    meta = payload.get("metadata")
    if isinstance(meta, dict):
        for key in ("retrieved_at", "timestamp", "completed_at"):
            if meta.get(key): return str(meta[key])
    return None


def _parameters(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict): return {}
    found = {k: payload[k] for k in PARAMETER_KEYS if k in payload and payload[k] not in (None, "", [], {})}
    meta = payload.get("metadata")
    if isinstance(meta, dict):
        found.update({f"metadata.{k}": meta[k] for k in PARAMETER_KEYS if k in meta and meta[k] not in (None, "", [], {})})
    return found


def _benchmarks(payload: Any) -> list[Any]:
    if not isinstance(payload, dict): return []
    refs = payload.get("benchmark_refs") or payload.get("benchmarks") or []
    if isinstance(refs, (str, dict)): refs = [refs]
    return list(refs) if isinstance(refs, list) else []


def _digest(payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def _source_nodes(context: dict, present: list[str]) -> list[dict]:
    out = []
    for section in present:
        payload = context.get(section)
        meta = SECTION_META.get(section, {"tool": section, "algorithm": section, "database": "recorded result"})
        out.append({
            "id": section,
            "tool": meta["tool"], "algorithm": meta["algorithm"], "database": meta["database"],
            "version": _version(payload), "parameters": _parameters(payload),
            "retrieved_at": _timestamp(payload), "recorded_at": _utc_now(),
            "evidence_class": classify_source(section, payload).value,
            "citation": SECTION_CITATIONS.get(section), "benchmark_refs": _benchmarks(payload),
            "payload_sha256": _digest(payload),
        })
    return out


def _link_claims(text: str, vocab: dict[str, list[str]], present: list[str], context: dict) -> list[dict]:
    claims = []
    for i, sentence in enumerate(sentence_split(text)):
        low = sentence.lower()
        evidence = [s for s in present if any(t.lower() in low for t in vocab.get(s, []) if t)]
        policy = classify_claim(sentence=sentence, evidence_sections=evidence, context=context)
        confidence = "high" if policy["admitted"] and len(evidence) >= 2 else ("medium" if policy["admitted"] else "none")
        claims.append({
            "id": f"claim-{i+1}", "text": sentence, "confidence": confidence,
            "evidence": evidence, "evidence_refs": evidence,
            "evidence_class": policy["evidence_class"], "numeric_claims": policy["numeric_claims"],
            "unsupported_numeric_claims": policy["unsupported_numeric_claims"],
            "rejected": not policy["admitted"], "rejection_reason": None if policy["admitted"] else policy["reason"],
        })
    return claims


def _typed_graph(claims: list[dict], sources: list[dict]) -> tuple[list[dict], list[dict]]:
    nodes, edges = [], []
    by_source = {s["id"]: s for s in sources}
    for claim in claims:
        cid = claim["id"]
        conf = _stable_id("confidence", cid, claim.get("confidence"))
        nodes += [
            {"id": cid, "type": "claim", "label": claim.get("text"), "data": claim},
            {"id": conf, "type": "confidence", "label": claim.get("confidence", "none"), "data": {"level": claim.get("confidence", "none"), "rejected": bool(claim.get("rejected"))}},
        ]
        edges.append({"from": cid, "to": conf, "relation": "has_confidence"})
        for sid in claim.get("evidence_refs", []):
            source = by_source.get(sid)
            if not source: continue
            evid = _stable_id("evidence", cid, sid); alg = _stable_id("algorithm", sid, source.get("algorithm"))
            db = _stable_id("database", sid, source.get("database")); ver = _stable_id("version", sid, source.get("version") or "not-recorded")
            par = _stable_id("parameters", sid, json.dumps(source.get("parameters") or {}, sort_keys=True, default=str))
            nodes += [
                {"id": evid, "type": "evidence", "label": sid, "data": {"section": sid, "evidence_class": source.get("evidence_class"), "citation": source.get("citation"), "payload_sha256": source.get("payload_sha256"), "retrieved_at": source.get("retrieved_at")}},
                {"id": alg, "type": "algorithm", "label": source.get("algorithm") or "not recorded", "data": {"tool": source.get("tool")}},
                {"id": db, "type": "database", "label": source.get("database") or "not recorded", "data": {}},
                {"id": ver, "type": "version", "label": source.get("version") or "not recorded", "data": {}},
                {"id": par, "type": "parameters", "label": "recorded parameters" if source.get("parameters") else "parameters not recorded", "data": source.get("parameters") or {}},
            ]
            edges += [
                {"from": cid, "to": evid, "relation": "supported_by"}, {"from": evid, "to": alg, "relation": "generated_by"},
                {"from": alg, "to": db, "relation": "uses_database"}, {"from": db, "to": ver, "relation": "has_version"},
                {"from": ver, "to": par, "relation": "executed_with"}, {"from": par, "to": conf, "relation": "contributes_to_confidence"},
            ]
            refs = source.get("benchmark_refs") or [None]
            for ref in refs:
                bid = _stable_id("benchmark", sid, ref or "not-recorded")
                nodes.append({"id": bid, "type": "benchmark", "label": str(ref) if ref is not None else "benchmark not recorded", "data": {"reference": ref, "status": "not_recorded" if ref is None else "recorded"}})
                edges.append({"from": conf, "to": bid, "relation": "evaluated_by"})
    return list({n["id"]: n for n in nodes}.values()), list({(e["from"], e["to"], e["relation"]): e for e in edges}.values())


def assemble_evidence(context: dict | None) -> dict:
    ctx = context or {}; present = [s for s in ctx if s != "interpret" and ctx.get(s)]
    sources = _source_nodes(ctx, present)
    interp = ctx.get("interpret")
    text = (interp.get("interpretation") or interp.get("text") or "") if isinstance(interp, dict) else (interp if isinstance(interp, str) else "")
    if not text: text = str(ctx.get("final_report") or "")
    claims = _link_claims(text, keyword_vocab(ctx), present, ctx)
    if not claims:
        claims = [{"id":"claim-0","text":str(text)[:200] or "No AI interpretation recorded.","confidence":"none","evidence":[],"evidence_refs":[],"evidence_class":"unsupported/insufficient evidence","numeric_claims":[],"unsupported_numeric_claims":[],"rejected":True,"rejection_reason":"no auditable interpretation was recorded"}]
    nodes, typed_edges = _typed_graph(claims, sources)
    legacy_edges = [{"from": sid, "to": c["id"], "relation": "supports"} for c in claims for sid in c.get("evidence", [])]
    rejected = sum(1 for c in claims if c.get("rejected")); counts = {}
    for n in nodes: counts[n["type"]] = counts.get(n["type"], 0) + 1
    return {
        "schema": "bionexus-evidence-graph/v3", "generated_at_utc": _utc_now(),
        "reviewer_path": ["claim","evidence","algorithm","database","version","parameters","confidence","benchmark"],
        "nodes": nodes, "typed_edges": typed_edges, "edges": legacy_edges,
        "sources": sources, "claims": claims,
        "summary": {"source_count":len(sources),"claim_count":len(claims),"node_count":len(nodes),"typed_edge_count":len(typed_edges),"node_type_counts":counts,"rejected_claim_count":rejected,"unsupported_claim_rate":rejected/len(claims) if claims else 0.0},
    }
