"""Universal AI interpretation for every tool result.

Call interpret_tool_result(tool_name, result_dict) after any tool finishes.
Returns a dict with headline, summary, findings, caveats — or None if the
LLM is unavailable or the call fails (never blocks the pipeline).
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Tool-specific prompt fragments. Each entry maps a tool name to a system
# instruction that tells the LLM what to look for in that tool's output.
_TOOL_PROMPTS: dict[str, str] = {
    "docking": (
        "You are a computational chemistry expert. A molecular docking run just "
        "completed using AutoDock Vina. Summarize: binding affinity of the best pose, "
        "pose cluster quality, key protein-ligand interactions (H-bonds, hydrophobic, "
        "pi-stacking), and whether the affinity suggests a promising lead. "
        "Be specific with numbers (kcal/mol, distances). 2-4 sentences max."
    ),
    "structure_prep": (
        "You are a structural bioinformatician. A structure preparation job just "
        "finished. Summarize: chain integrity status, number and sizes of pockets "
        "found by fpocket, surface accessibility. Flag any issues (broken chains, "
        "missing residues). 2-3 sentences max."
    ),
    "function_predict": (
        "You are a protein biochemist. A function prediction just completed using "
        "InterProScan5 with InterPro2GO mapping. Summarize the top GO terms by "
        "category (molecular function, biological process, cellular component), "
        "key domains found, and what they suggest about protein function. "
        "2-4 sentences max."
    ),
    "pathway_enrichment": (
        "You are a systems biologist. A pathway enrichment analysis just completed "
        "using Reactome and/or g:Profiler. Summarize the most significant pathways "
        "identified, their FDR-corrected p-values, gene ratios, and what biological "
        "processes they collectively point to. 2-4 sentences max."
    ),
    "interactions": (
        "You are a network biologist. A protein-protein interaction analysis just "
        "completed using the STRING database. Summarize the top interaction partners, "
        "their combined scores, and what functional modules or complexes they suggest. "
        "2-3 sentences max."
    ),
    "ngs": (
        "You are a genomics analyst. An NGS analysis pipeline just completed "
        "(QC, alignment, variant calling, annotation). Summarize: read quality, "
        "mapping rate, number of variants called, known vs novel variants, and "
        "any flags the user should pay attention to. 3-5 sentences max."
    ),
    "sequencing": (
        "You are a genomics analyst. A sequencing analysis just completed. "
        "Summarize QC metrics, alignment results, variant calls, and any "
        "concerns about data quality. 2-4 sentences max."
    ),
    "md": (
        "You are a computational biophysicist. A molecular dynamics simulation "
        "just completed. Summarize the simulation parameters, energy minimization "
        "result, key structural observations, and whether the simulation converged. "
        "2-3 sentences max."
    ),
    "phylo": (
        "You are an evolutionary biologist. A phylogenetic analysis just completed. "
        "Summarize the tree topology, method used, bootstrap support if available, "
        "and what evolutionary relationships are revealed. 2-3 sentences max."
    ),
    "alignment": (
        "You are a sequence analyst. A multiple sequence or pairwise alignment just "
        "completed. Summarize the alignment length, percent identity, gaps, scoring "
        "matrix used, and what the alignment reveals about sequence conservation. "
        "2-3 sentences max."
    ),
    "admet": (
        "You are a medicinal chemist. An ADMET property prediction just completed. "
        "Summarize absorption, distribution, metabolism, excretion, and toxicity "
        "profiles. Flag any Lipinski violations or red flags for drug-likeness. "
        "2-3 sentences max."
    ),
    "primers": (
        "You are a molecular biologist. A primer design just completed. Summarize "
        "the primer pairs, Tm values, GC content, expected product sizes, and "
        "whether the primers look suitable for PCR. 2-3 sentences max."
    ),
    "castp": (
        "You are a structural bioinformatician. A CASTp pocket analysis just "
        "completed. Summarize the number of pockets found, their sizes (by atom "
        "count), and what functional sites they may correspond to. 2-3 sentences max."
    ),
    "swissmodel": (
        "You are a structural biologist. A homology modeling job just completed "
        "using SWISS-MODEL. Summarize the template used, sequence coverage, "
        "QMEANDiscore, and model quality. 2-3 sentences max."
    ),
    "structure_predict": (
        "You are a structural biologist. An AlphaFold structure prediction just "
        "completed. Summarize the pLDDT confidence, structure availability, and "
        "what regions are well-predicted vs disordered. 2-3 sentences max."
    ),
    "blast": (
        "You are a bioinformatician. A BLAST search just completed. Summarize how "
        "many database hits were found, the top hit (accession and description), its "
        "E-value, percent identity and bit score, and what these numbers mean for how "
        "confidently the query matches a known sequence. Explain in plain language. "
        "3-4 sentences max."
    ),
    "msa": (
        "You are a sequence analyst. A multiple sequence alignment just completed. "
        "Summarize the number of sequences aligned, alignment length, percent identity, "
        "gaps introduced, and which regions are highly conserved. Explain what the "
        "conservation suggests functionally, in plain language. 2-3 sentences max."
    ),
    "dotplot": (
        "You are a bioinformatician. A dot plot comparison of two sequences just "
        "completed. Summarize the lengths of the two sequences, how many dots/matches "
        "were found, the percentage on the main diagonal, and whether any repeats "
        "(off-diagonal), inverted repeats (anti-diagonal), or indel gaps were detected. "
        "Explain what this reveals about sequence similarity and repeats, in plain "
        "language. 3-4 sentences max."
    ),
    "domains": (
        "You are a protein bioinformatician. A PROSITE motif/domain scan just "
        "completed. Summarize how many domains or motifs were found, the names and "
        "positions of the most important ones, and what they suggest about the "
        "protein's function. 2-3 sentences max."
    ),
    "motif": (
        "You are a sequence analyst. A motif/pattern scan just completed. Summarize "
        "which patterns were searched, how many matches were found and where, and "
        "what they suggest about the sequence. 2-3 sentences max."
    ),
    "structure": (
        "You are a structural bioinformatician. A protein structure lookup just "
        "completed. Summarize the PDB ID, method (X-ray, cryo-EM, etc.), resolution, "
        "title, and what the structure represents. Note the reliability (resolution or "
        "confidence). 2-3 sentences max."
    ),
    "uniprot": (
        "You are a protein bioinformatician. A UniProt record was just retrieved. "
        "Summarize the protein name, organism, gene, its known function, subcellular "
        "location, and any domains or active sites. Explain the key function in plain "
        "language. 3-4 sentences max."
    ),
    "pairwise_alignment": (
        "You are a sequence analyst. A pairwise sequence alignment just completed. "
        "Summarize the method (global or local), scoring matrix, alignment length, "
        "percent identity and similarity, gaps, and what the alignment says about how "
        "similar the two sequences are. 2-3 sentences max."
    ),
    "pathway": (
        "You are a molecular biologist. A pathway search just completed. Summarize "
        "how many pathways were found, the names of the top ones, and what their "
        "functions are in plain language. Explain why the searched genes or proteins "
        "are associated with these pathways. 3-4 sentences max."
    ),
    "sequences": (
        "You are a sequence analyst. An automatic sequence analysis just completed. "
        "Summarize the sequence type (protein or nucleotide), its length, composition "
        "details, and the most notable computed properties or warnings. Explain what "
        "these mean in plain language. 2-3 sentences max."
    ),
}


def _summarize_result(result: dict, max_keys: int = 15) -> str:
    """Extract a compact text summary of a result dict for the LLM prompt."""
    parts: list[str] = []
    for k, v in list(result.items())[:max_keys]:
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            parts.append(f"{k}: {v}")
        elif isinstance(v, list) and len(v) > 0:
            if isinstance(v[0], dict):
                parts.append(f"{k}: [{len(v)} items] first={json.dumps(v[0], default=str)[:200]}")
            else:
                parts.append(f"{k}: {str(v)[:200]}")
        elif isinstance(v, dict):
            inner = json.dumps(v, default=str)[:300]
            parts.append(f"{k}: {inner}")
        else:
            parts.append(f"{k}: {str(v)[:200]}")
    return "\n".join(parts)


async def interpret_tool_result(tool_name: str, result: dict) -> dict | None:
    """Generate an AI interpretation of a tool's result.

    Returns {headline, summary, findings: list[str], caveats: list[str]}
    or None if interpretation is unavailable (never raises).
    """
    system_prompt = _TOOL_PROMPTS.get(tool_name)
    if not system_prompt:
        return None

    try:
        from app.ai.llm_client import llm_client
        if not llm_client.has_api_key():
            return None
    except Exception:
        return None

    result_text = _summarize_result(result)

    user_prompt = (
        f"Tool: {tool_name}\n"
        f"Results:\n{result_text}\n\n"
        "You are explaining these results to a non-expert with no prior knowledge of "
        "bioinformatics or chemistry. Write in plain, simple language. When you must "
        "use a technical term (E-value, RMSD, bootstrap, kcal/mol, TPSA, etc.), briefly "
        "explain what it means in everyday words right after using it.\n\n"
        "Return a JSON object with exactly these keys:\n"
        '  "headline": one sentence plain-language summary (max 12 words)\n'
        '  "summary": 2-5 sentence interpretation a complete beginner can understand\n'
        '  "findings": list of 2-4 key observations, each written simply\n'
        '  "caveats": list of 0-3 caveats or limitations\n'
        "Return ONLY the JSON, no markdown fences."
    )

    try:
        from app.ai.interpreter import _get_acompletion
        acompletion = _get_acompletion()
        if acompletion is None:
            return None

        candidates = llm_client.get_all_candidates()
        if not candidates:
            return None

        last_error = None
        for candidate in candidates:
            for attempt in range(2):
                try:
                    response = await acompletion(
                        model=candidate["model"],
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        max_tokens=2000,
                        temperature=0.3,
                        timeout=60,
                        api_key=candidate["api_key"],
                    )
                    response_text = response.choices[0].message.content or ""
                    if not response_text:
                        return None

                    text = response_text.strip()
                    if text.startswith("```"):
                        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

                    parsed = json.loads(text)
                    return {
                        "headline": str(parsed.get("headline", "")),
                        "summary": str(parsed.get("summary", "")),
                        "findings": [str(f) for f in (parsed.get("findings") or [])],
                        "caveats": [str(c) for c in (parsed.get("caveats") or [])],
                    }
                except json.JSONDecodeError:
                    logger.debug("AI interpretation response was not valid JSON for tool %s", tool_name)
                    return None
                except Exception as e:
                    last_error = e
                    if attempt < 1:
                        continue
        logger.debug("AI interpretation failed for tool %s: %s", tool_name, last_error)
        return None
    except Exception as e:
        logger.debug("AI interpretation failed for tool %s: %s", tool_name, e)
        return None
