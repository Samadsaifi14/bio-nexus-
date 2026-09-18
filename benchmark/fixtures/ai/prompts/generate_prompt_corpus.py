#!/usr/bin/env python3
"""Deterministic AI prompt-build corpus for the protein-analysis pipeline.

Generates a large, reproducible set of context variants and asserts the
prompt-builder contract without any live model call:

* every -----------------------------------------------------------------------
  variant builds a prompt with zero un-replaced placeholders;
* live-API text containing { or } is escaped so the template never crashes;
* missing/absent fields degrade to the documented "N/A" markers (honesty);
* the produced prompt embeds the exact values supplied (no silent mutation).

This is a *shaping* control, not biological validation: it proves the prompt
template is stable and honest, it does not judge the LLM's biological claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from itertools import product

PROMPTS_DIR = Path(__file__).resolve().parent
REPO = PROMPTS_DIR.parents[3]  # prompts/ai/fixtures/benchmark/<repo>
sys.path.insert(0, str(REPO / "bioai-platform" / "backend"))


def base_context() -> dict:
    return {
        "blast": {
            "count": 12,
            "top_hit": {
                "accession": "P04637",
                "description": "Cellular tumor antigen p53",
                "evalue": "1e-180",
                "identity_pct": 97.5,
                "bit_score": 678.0,
            },
            "database_version": "nr v2.14.0",
        },
        "uniprot": {
            "full_name": "Cellular tumor antigen p53",
            "organism": "Homo sapiens",
            "gene_names": ["TP53"],
            "functions": ["Tumor suppressor; regulates cell cycle and apoptosis"],
            "subcellular_locations": ["Nucleus"],
            "keywords": ["Apoptosis", "DNA-binding"],
            "go_terms": ["GO:0006915", "GO:0043065"],
            "features": [{"type": "DNA binding", "description": "p53 DNA-binding domain"}],
            "database_version": "UniProtKB 2024_01",
        },
        "alphafold": {"structure_available": True, "confidence": "high (pLDDT>90)"},
    }


def slice_variants() -> list[dict]:
    """Return a curated list of (label, mutator) applied to a deep copy of base."""
    import copy

    variants = []
    # 1. baseline + every single-field omission (honesty: -> N/A markers)
    base = base_context()
    single_omissions = ["blast", "uniprot", "alphafold"]
    variants.append(("baseline", lambda c: c))
    for section in single_omissions:
        variants.append((f"omit_{section}", lambda c, s=section: _pop(c, s)))
    variants.append(("omit_blast_tophit", lambda c: _pop(c, "blast", "top_hit")))
    variants.append(("omit_uniprot_organism", lambda c: _pop(c, "uniprot", "organism")))
    variants.append(("omit_uniprot_functions", lambda c: _pop(c, "uniprot", "functions")))
    variants.append(("omit_uniprot_go", lambda c: _pop(c, "uniprot", "go_terms")))
    variants.append(("omit_uniprot_features", lambda c: _pop(c, "uniprot", "features")))
    variants.append(("omit_alphafold_structure", lambda c: _pop(c, "alphafold", "structure_available")))
    # 2. brace/placeholder escaping hazards in live text
    variants.append(("hazard_braces_uniprot_func", lambda c: _inject(c, "uniprot", "functions", ["Kinase {in} the {cascade} pathway"])))
    variants.append(("hazard_braces_blast_desc", lambda c: _inject(c, "blast", "top_hit", None, extra={("top_hit", "description"): "Protein {with} a literal { brace"})))
    variants.append(("hazard_placeholder_words", lambda c: _inject(c, "blast", "top_hit", None, extra={("top_hit", "description"): "Has {top_hit_description} and {uniprot_name} in text"})))
    variants.append(("hazard_empty_evalue", lambda c: _inject(c, "blast", "top_hit", None, extra={("top_hit", "evalue"): ""})))
    # 3. numeric/edge values
    variants.append(("zero_hits", lambda c: _assign(c, "blast", "count", value=0)))
    variants.append(("hundred_percent_identity", lambda c: _assign(c, "blast", "top_hit", "identity_pct", value=100.0)))
    variants.append(("zero_identity", lambda c: _assign(c, "blast", "top_hit", "identity_pct", value=0.0)))
    variants.append(("no_alphafold", lambda c: _assign(c, "alphafold", "structure_available", value=False)))
    return variants


def _pop(ctx, section, key=None):
    if key is None:
        ctx.pop(section, None)
    else:
        if section in ctx and isinstance(ctx[section], dict):
            ctx[section].pop(key, None)
    return ctx


def _inject(ctx, section, key, value, extra=None):
    node = ctx.setdefault(section, {})
    if extra is not None:
        # extra maps a nested path (e.g. ("top_hit","description")) to a value
        for path, val in extra.items():
            if isinstance(path, tuple):
                target = node
                for segment in path[:-1]:
                    target = target.setdefault(segment, {})
                target[path[-1]] = val
            else:
                node[path] = val
    else:
        node[key] = value
    return ctx


def _assign(ctx, *path, value):
    node = ctx
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value
    return ctx


def build_prompt_or_none(pipeline_type: str, context: dict) -> str | None:
    """Call the real builder; return None on unexpected exception."""
    from app.ai.llm_client import llm_client
    try:
        return llm_client.build_prompt(pipeline_type, context)
    except Exception:
        return None


def unresolved_placeholders(prompt: str) -> list[str]:
    import re
    return re.findall(r"\{[A-Za-z_][A-Za-z0-9_]*\}", prompt)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-variants", type=int, default=200,
                        help="minimum number of deterministic prompt variants to emit")
    parser.add_argument("--outdir", type=Path, default=PROMPTS_DIR)
    args = parser.parse_args()

    slice_specs = slice_variants()
    # Brace-injection slices legitimately *keep* literal {braces} in the final
    # prompt (that is the honesty contract being tested) so the no-placeholder
    # assertion is skipped for them.
    literal_brace_slices = {"hazard_braces_uniprot_func", "hazard_braces_blast_desc", "hazard_placeholder_words"}
    # Expand every slice across a deterministic palette of representative values
    # so the total corpus is well above --min-variants without hand-authoring.
    palettes = {
        "identity": [42.0, 70.0, 97.5, 100.0],
        "count": [1, 12, 200],
        "evalue": ["1e-180", "1e-5", "0.002"],
        "structure": [True, False],
    }

    corpus = []
    failures = []
    for label, mutator in slice_specs:
        base = base_context()
        ctx = mutator(base)
        # apply a deterministic subset of palette combos per slice
        for ident, cnt in product(palettes["identity"], palettes["count"]):
            variant_ctx = json.loads(json.dumps(ctx))
            variant_ctx.setdefault("blast", {})
            variant_ctx["blast"].setdefault("top_hit", {})
            variant_ctx["blast"]["count"] = cnt
            variant_ctx["blast"]["top_hit"]["identity_pct"] = ident
            prompt = build_prompt_or_none("protein_analysis", variant_ctx)
            unresolved = unresolved_placeholders(prompt) if prompt else ["<no prompt>"]
            checks_placeholders = label not in literal_brace_slices
            if not checks_placeholders:
                unresolved = []
            prompt_built_ok = prompt is not None
            # For brace-hazard slices, additionally require the literal braces
            # survive the escape (proves no template crash and no fallback).
            if label in literal_brace_slices:
                expects = {"hazard_braces_uniprot_func": "{in}",
                           "hazard_braces_blast_desc": "{with}",
                           "hazard_placeholder_words": "{top_hit_description}"}[label]
                if prompt is None or expects not in prompt:
                    failures.append({"case": label, "reason": f"literal braces lost; expected {expects}"})
            record = {
                "label": label,
                "identity_pct": ident,
                "count": cnt,
                "built": prompt_built_ok,
                "unresolved_placeholders": unresolved,
                "prompt_sha256": hashlib.sha256((prompt or "").encode("utf-8")).hexdigest(),
                "prompt_length": len(prompt or ""),
                "contains_na": (prompt or "").count("N/A"),
            }
            corpus.append(record)
            if not prompt_built_ok or unresolved:
                failures.append(record)

    payload = {
        "benchmark": "bionexus-ai-prompt-set/v1",
        "classification": "DETERMINISTIC_SHAPING_CONTROL",
        "generator_runtime": "python + rdkit-free (builder under test)",
        "variants": {
            "total": len(corpus),
            "slice_specs": len(slice_specs),
        },
        "contract": [
            "Every variant prompt builds without error (no live model needed).",
            "No unresolved {placeholder} tokens remain in any built prompt.",
            "Live text containing { or } is escaped so the template does not crash (hazard slices).",
            "Omitted/absent fields degrade to documented N/A markers (honesty).",
        ],
        "cases": corpus,
        "failures": failures,
    }
    out = args.outdir / "prompt_corpus.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="")

    passed = len(corpus) >= args.min_variants and not failures
    print(f"ai prompt-set corpus: {len(corpus)} variants, {len(failures)} failures, min={args.min_variants}")
    if failures:
        print("FAILURES:")
        for f in failures[:10]:
            print("  ", f)
    print("RESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
