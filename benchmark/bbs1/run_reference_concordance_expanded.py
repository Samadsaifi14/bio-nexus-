"""Expanded BBS-1 external/reference concordance suite.

This is the publication-scale companion to run_reference_concordance.py.  It increases
sample diversity without changing the scientific claim boundary: passing means that the
BioNexus integration preserves the selected reference outputs for the tested cases.

The suite deliberately reports each case and never converts a network/service failure into
a biological negative.  Network-backed experiments may therefore fail transiently and
should be repeated only as a new, timestamped run rather than overwritten.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
from datetime import datetime, timezone
from pathlib import Path

import httpx

import run_reference_concordance as base
from app.tools.blast import BlastTool

ADMET_CASES = {
    "ethanol": "CCO", "methanol": "CO", "acetone": "CC(=O)C", "acetic_acid": "CC(=O)O",
    "benzene": "c1ccccc1", "toluene": "Cc1ccccc1", "phenol": "Oc1ccccc1", "aniline": "Nc1ccccc1",
    "glycine": "NCC(=O)O", "alanine": "CC(N)C(=O)O", "urea": "NC(=O)N", "ethyl_acetate": "CCOC(=O)C",
    "aspirin": "CC(=O)OC1=CC=CC=C1C(=O)O", "caffeine": "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
    "acetaminophen": "CC(=O)NC1=CC=C(C=C1)O", "ibuprofen": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
    "salicylic_acid": "O=C(O)c1ccccc1O", "benzoic_acid": "O=C(O)c1ccccc1",
    "pyridine": "n1ccccc1", "cyclohexane": "C1CCCCC1",
}

UNIPROT_CASES = (
    "P69905", "P68871", "P04637", "P00533", "P38398",
    "P51587", "P01308", "P60709", "P02768", "P01116",
)

RCSB_CASES = ("1CRN", "4HHB", "1UBQ", "1AKE", "1BNA")
BLAST_TARGETS = ("P68871", "P69905", "P04637")
PRIMER_SEEDS = tuple(20260904 + i for i in range(10))


def run_admet_expanded() -> dict:
    original = base.ADMET_CASES
    try:
        base.ADMET_CASES = ADMET_CASES
        return base.run_admet()
    finally:
        base.ADMET_CASES = original


async def run_uniprot_expanded() -> dict:
    original = base.UNIPROT_CASES
    try:
        base.UNIPROT_CASES = UNIPROT_CASES
        return await base.run_uniprot()
    finally:
        base.UNIPROT_CASES = original


async def run_rcsb_expanded() -> dict:
    original = base.RCSB_CASES
    try:
        base.RCSB_CASES = RCSB_CASES
        return await base.run_rcsb()
    finally:
        base.RCSB_CASES = original


async def run_blast_expanded() -> dict:
    cases = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for accession in BLAST_TARGETS:
            raw = (await client.get(f"https://rest.uniprot.org/uniprotkb/{accession}.json")).json()
            sequence = (raw.get("sequence") or {}).get("value", "")
            if not sequence:
                cases.append({"accession": accession, "passed": False, "error": "UniProt returned no sequence"})
                continue
            observed = await BlastTool().run_uncached({
                "sequence": sequence, "program": "blastp", "database": "uniprotkb_swissprot", "max_hits": 10,
            })
            hits = observed.get("hits") or []
            accessions = [str(h.get("accession") or "") for h in hits]
            identities = [float(h.get("identity_pct") or 0) for h in hits]
            target_present = any(a == accession or accession in a for a in accessions)
            max_identity = max(identities, default=0.0)
            passed = observed.get("error") is None and target_present and max_identity >= 99.0
            cases.append({"accession": accession, "passed": passed, "target_present": target_present,
                          "max_identity_pct": max_identity, "top_accessions": accessions,
                          "error": observed.get("error")})
    return {"name": "Expanded live EBI BLAST known-sequence recovery", "passed": all(c["passed"] for c in cases),
            "reference": "EMBL-EBI BLAST against UniProtKB/Swiss-Prot", "case_count": len(cases), "cases": cases,
            "scope_note": "Criterion is exact-accession recovery in the first ten hits with >=99% maximum identity; rank is not frozen."}


def _template_for_seed(seed: int) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(800))


async def run_primer3_expanded() -> dict:
    original = base._primer_template
    cases = []
    try:
        for seed in PRIMER_SEEDS:
            base._primer_template = lambda seed=seed: _template_for_seed(seed)
            result = await base.run_primer3()
            cases.append({"seed": seed, "passed": result["passed"], "returned_pairs": result["returned_pairs"],
                          "template_sha256": result["template_sha256"], "comparisons": result["comparisons"]})
    finally:
        base._primer_template = original
    return {"name": "Expanded Primer3 integration parity", "reference": "direct primer3-py call",
            "passed": all(c["passed"] for c in cases), "case_count": len(cases), "cases": cases,
            "scope_note": "Ten deterministic templates test integration parity; no wet-lab specificity claim is made."}


async def main(output: Path) -> int:
    experiments = []
    for fn in (run_admet_expanded,): experiments.append(fn())
    for fn in (run_uniprot_expanded, run_rcsb_expanded, run_blast_expanded, run_primer3_expanded):
        try: experiments.append(await fn())
        except Exception as exc: experiments.append({"name": fn.__name__, "passed": False, "error": repr(exc)})
    # Keep the original independently submitted Clustal Omega experiment as an additional
    # algorithm-level parity check. It is intentionally not inflated into pseudo-replicates.
    try: experiments.append(await base.run_msa())
    except Exception as exc: experiments.append({"name": "Clustal Omega MSA integration parity", "passed": False, "error": repr(exc)})

    result = {
        "suite": "BioNexus Benchmark Suite v1.0 expanded external concordance",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_design": {"admet_molecules": len(ADMET_CASES), "uniprot_accessions": len(UNIPROT_CASES),
                        "rcsb_structures": len(RCSB_CASES), "blast_targets": len(BLAST_TARGETS),
                        "primer_templates": len(PRIMER_SEEDS), "msa_sets": 1},
        "experiments": experiments,
        "passed": all(bool(e.get("passed")) for e in experiments),
        "claim_boundary": "This expanded suite is an integration-concordance benchmark, not a clinical, wet-lab, docking-affinity or universal biological-accuracy benchmark.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--output", type=Path, default=Path("results/reference_concordance_expanded.json"))
    args = p.parse_args(); raise SystemExit(asyncio.run(main(args.output)))
