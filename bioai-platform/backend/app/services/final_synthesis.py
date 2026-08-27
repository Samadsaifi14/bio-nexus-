"""Final synthesis — techspec.md §3.

Builds a single structured "Final Report" for a completed pipeline run:
one headline, per-finding claims each tagged with the run's confidence tier
(identified / homolog / de_novo), and honest caveats.

An LLM pass polishes the wording when a provider is reachable; the findings
and caveats themselves are always assembled deterministically from real step
results, so the panel never invents content and never blocks the pipeline.
"""

import logging

logger = logging.getLogger(__name__)

_CAVEATS = {
    "identified": [
        "Annotations describe the matched database entry — transferability to your exact input depends on sequence identity.",
    ],
    "homolog": [
        "The query was resolved via sequence similarity, so annotations describe a homolog, not the exact protein.",
        "Verify functional transferability before relying on homolog-derived annotations experimentally.",
    ],
    "de_novo": [
        "No database match was found — every annotation is a computational prediction on the raw sequence.",
        "Treat composition- and structure-based hints as hypotheses for experimental follow-up.",
    ],
}


def _tier(context: dict) -> str:
    return (context.get("query") or {}).get("confidence") or "identified"


def build_findings(context: dict) -> tuple[list[dict], list[dict]]:
    """Deterministic findings + stats from actual step results."""
    tier = _tier(context)
    findings: list[dict] = []
    stats = context.get("query", {})

    blast = context.get("blast") or {}
    top_hit = blast.get("top_hit")
    if top_hit:
        findings.append({
            "claim": f"Closest database match: {top_hit.get('description', 'unknown')} ({top_hit.get('accession', '?')})",
            "confidence_tier": tier,
            "source_tool": "blast",
            "page_url": f"https://www.ncbi.nlm.nih.gov/protein/{top_hit.get('accession', '')}" if top_hit.get("accession") else None,
        })
    elif blast.get("count", 0) == 0:
        findings.append({
            "claim": "No significant similarity to any database sequence.",
            "confidence_tier": tier,
            "source_tool": "blast",
            "page_url": None,
        })

    uniprot = context.get("uniprot") or {}
    if uniprot.get("_de_novo"):
        comp = uniprot.get("composition") or {}
        findings.append({
            "claim": (
                f"De novo characterization: {comp.get('sequence_type', 'protein')} of "
                f"{comp.get('length', stats.get('length', '?'))} residues; function hints are heuristic only."
            ),
            "confidence_tier": tier,
            "source_tool": "uniprot",
            "page_url": None,
        })
    elif uniprot and not uniprot.get("error"):
        name = uniprot.get("full_name") or uniprot.get("accession") or "entry"
        findings.append({
            "claim": f"Annotated as {name} ({uniprot.get('accession', '?')}) in UniProt.",
            "confidence_tier": tier,
            "source_tool": "uniprot",
            "page_url": f"https://www.uniprot.org/uniprotkb/{uniprot.get('accession', '')}" if uniprot.get("accession") else None,
        })

    domains = context.get("domains") or {}
    dom_list = domains.get("domains") or []
    if dom_list:
        top_domain = dom_list[0]
        findings.append({
            "claim": (
                f"{len(dom_list)} domain(s) detected — top: {top_domain.get('name', '?')} "
                f"({top_domain.get('source_db', '?')})."
            ),
            "confidence_tier": tier,
            "source_tool": "domains",
            "page_url": (
                f"https://www.ebi.ac.uk/interpro/entry/InterPro/{top_domain['accession']}"
                if top_domain.get("accession") else None
            ),
        })

    msa = context.get("msa") or {}
    if msa.get("aln_fasta"):
        findings.append({
            "claim": f"Multiple sequence alignment built over {msa.get('sequence_count', '?')} sequences.",
            "confidence_tier": tier,
            "source_tool": "msa",
            "page_url": None,
        })

    pathway = context.get("pathway_enrichment") or {}
    pw_list = (pathway.get("pathways") if isinstance(pathway, dict) else None) or []
    if pw_list:
        top_pw = pw_list[0]
        st_id = top_pw.get("stId", "")
        findings.append({
            "claim": (
                f"Pathway enrichment: {len(pw_list)} Reactome pathway(s), "
                f"e.g. {top_pw.get('name', '?')} (FDR {top_pw.get('entitiesFDR', '?')})."
            ),
            "confidence_tier": tier,
            "source_tool": "pathway_enrichment",
            "page_url": f"https://reactome.org/PathwayBrowser/#{st_id}" if st_id else None,
        })
    elif isinstance(pathway, dict) and pathway.get("error"):
        findings.append({
            "claim": f"Pathway enrichment unavailable ({str(pathway.get('error'))[:80]}).",
            "confidence_tier": tier,
            "source_tool": "pathway_enrichment",
            "page_url": None,
        })

    af = context.get("alphafold") or {}
    if af.get("structure_available"):
        source_label = "ESMFold prediction" if af.get("source") == "esmfold" else "AlphaFold DB model"
        plddt = af.get("mean_plddt") or af.get("confidence")
        detail = f", mean pLDDT {plddt}" if plddt else ""
        findings.append({
            "claim": f"3D structure available ({source_label}{detail}).",
            "confidence_tier": tier,
            "source_tool": "alphafold",
            "page_url": af.get("pdb_url"),
        })

    return findings, [f"Confidence tier for this run: {tier}."] + _CAVEATS.get(tier, [])


def _headline(context: dict, findings: list[dict]) -> str:
    tier = _tier(context)
    if tier == "de_novo":
        return "Novel sequence — characterized de novo from composition and predicted structure."
    top = next((f for f in findings if f["source_tool"] == "uniprot"), None)
    if top:
        return f"Identified with {tier}-confidence annotation: {top['claim'].removeprefix('Annotated as ').rstrip('.')}"
    hit = next((f for f in findings if f["source_tool"] == "blast"), None)
    return hit["claim"] if hit else "Analysis complete."


async def _polish_with_llm(headline: str, summary_parts: list[str]) -> str | None:
    """Best-effort LLM rewrite of the headline+summary. Returns None on failure."""
    try:
        from app.ai.interpreter import _get_acompletion
        from app.ai import llm_client

        acompletion = _get_acompletion()
        candidates = llm_client.get_all_candidates()
        if acompletion is None or not candidates:
            return None

        prompt = (
            "Rewrite the following research summary into ONE crisp paragraph (max 90 words).\n"
            "Do not add facts that are not present. Keep hedged language.\n\n"
            f"Headline: {headline}\nFindings:\n- " + "\n- ".join(summary_parts)
        )
        candidate = candidates[0]
        response = await acompletion(
            model=candidate["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000,
            timeout=20,
            api_key=candidate["api_key"],
        )
        text = response.choices[0].message.content if response.choices else ""
        return text.strip() or None
    except Exception as exc:
        logger.info("Synthesis LLM polish skipped: %s", exc)
        return None


async def synthesize(context: dict) -> dict:
    """Produce the final_report block stored in context_json."""
    findings, caveats = build_findings(context)
    headline = _headline(context, findings)

    polished = await _polish_with_llm(
        headline, [f["claim"] for f in findings] if findings else ["No significant results."]
    )
    report = {
        "headline": headline,
        "summary": polished or " ".join(f["claim"] for f in findings if f["source_tool"] == "blast")
        or "Analysis complete — see per-tool sections below.",
        "findings": findings,
        "caveats": caveats,
        "_mode": "llm_polished" if polished else "deterministic",
    }
    logger.info(
        "Final synthesis built (%s): %d findings",
        report["_mode"],
        len(findings),
    )
    return report


def synthesize_sync(context: dict) -> dict:
    """Synchronous variant (no LLM polish) for export paths."""
    findings, caveats = build_findings(context)
    return {
        "headline": _headline(context, findings),
        "summary": " ".join(f["claim"] for f in findings[:3]),
        "findings": findings,
        "caveats": caveats,
        "_mode": "deterministic",
    }
