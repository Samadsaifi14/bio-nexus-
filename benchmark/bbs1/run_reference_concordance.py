"""BBS-1 external/reference concordance experiment.

This script compares BioNexus deterministic outputs with independently queried
reference sources or the underlying scientific library. It writes JSON suitable
for retention as a benchmark artifact. Network-backed cases fail explicitly;
no unavailable source is converted into a passing result.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from rdkit import Chem, rdBase
from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors

from app.tools.admet import compute_descriptors
from app.tools.uniprot import UniprotTool
from app.tools.docking import fetch_pdb_from_rcsb
from app.tools.blast import BlastTool


ADMET_CASES = {
    "aspirin": "CC(=O)OC1=CC=CC=C1C(=O)O",
    "caffeine": "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
    "acetaminophen": "CC(=O)NC1=CC=C(C=C1)O",
    "ibuprofen": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
    "ethanol": "CCO",
}

UNIPROT_CASES = ("P69905", "P68871", "P04637")
RCSB_CASES = ("1CRN", "4HHB")
HBB_SEQUENCE = "MVHLTPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRFFESFGDLSTPDAVMGNPKVKAHGKKVLGAFSDGLAHLDNLKGTFATLSELHCDKLHVDPENFRLLGNVLVCVLAHHFGKEFTPPVQAAYQKVVAGVANALAHKYH"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _admet_reference(smiles: str) -> dict:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"RDKit rejected benchmark SMILES: {smiles}")
    return {
        "molecular_weight": round(Descriptors.MolWt(mol), 2),
        "logp": round(Descriptors.MolLogP(mol), 2),
        "tpsa": round(Descriptors.TPSA(mol, includeSandP=True), 2),
        "hbd": int(Lipinski.NumHDonors(mol)),
        "hba": int(rdMolDescriptors.CalcNumLipinskiHBA(mol)),
        "rotatable_bonds": int(Lipinski.NumRotatableBonds(mol)),
        "heavy_atoms": int(mol.GetNumHeavyAtoms()),
    }


def run_admet() -> dict:
    cases = []
    all_pass = True
    for name, smiles in ADMET_CASES.items():
        observed = compute_descriptors(smiles)
        reference = _admet_reference(smiles)
        fields = {}
        case_pass = True
        for field, expected in reference.items():
            actual = observed.get(field)
            passed = actual == expected
            if isinstance(expected, float) and isinstance(actual, (int, float)):
                passed = abs(float(actual) - expected) <= 1e-12
            fields[field] = {
                "bionexus": actual,
                "reference_rdkit": expected,
                "passed": passed,
            }
            case_pass &= passed
        all_pass &= case_pass
        cases.append({"case": name, "smiles": smiles, "passed": case_pass, "fields": fields})
    return {
        "name": "ADMET core descriptor concordance",
        "reference": "same installed RDKit public descriptor functions",
        "passed": all_pass,
        "case_count": len(cases),
        "cases": cases,
        "scope_note": "Only deterministic RDKit-derived quantities are validated here. Heuristic ADMET/toxicity labels are not treated as experimentally validated predictions.",
    }


async def run_uniprot() -> dict:
    tool = UniprotTool()
    cases = []
    all_pass = True
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for accession in UNIPROT_CASES:
            observed = await tool.run({"accession": accession})
            response = await client.get(f"https://rest.uniprot.org/uniprotkb/{accession}.json")
            response.raise_for_status()
            raw = response.json()
            raw_entry_type = (raw.get("entryType") or "").lower()
            expected = {
                "accession": raw.get("primaryAccession", ""),
                "sequence": (raw.get("sequence") or {}).get("value", ""),
                "sequence_length": (raw.get("sequence") or {}).get("length", 0),
                "organism": (raw.get("organism") or {}).get("scientificName", ""),
                "reviewed": "reviewed" in raw_entry_type and "unreviewed" not in raw_entry_type,
            }
            fields = {}
            case_pass = True
            for field, expected_value in expected.items():
                actual = observed.get(field)
                passed = actual == expected_value
                fields[field] = {"bionexus": actual, "reference_uniprot": expected_value, "passed": passed}
                case_pass &= passed
            all_pass &= case_pass
            cases.append({"accession": accession, "passed": case_pass, "fields": fields})
    return {
        "name": "UniProt field concordance",
        "reference": "UniProt REST API raw JSON",
        "passed": all_pass,
        "case_count": len(cases),
        "cases": cases,
    }


async def run_rcsb() -> dict:
    cases = []
    all_pass = True
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for pdb_id in RCSB_CASES:
            observed = fetch_pdb_from_rcsb(pdb_id)
            response = await client.get(f"https://files.rcsb.org/download/{pdb_id}.pdb")
            response.raise_for_status()
            reference = response.text
            observed_atoms = sum(1 for line in observed.splitlines() if line.startswith(("ATOM  ", "HETATM")))
            reference_atoms = sum(1 for line in reference.splitlines() if line.startswith(("ATOM  ", "HETATM")))
            passed = (
                observed_atoms == reference_atoms
                and observed_atoms > 0
                and _sha256_text(observed.strip()) == _sha256_text(reference.strip())
            )
            all_pass &= passed
            cases.append({
                "pdb_id": pdb_id,
                "passed": passed,
                "bionexus_atom_records": observed_atoms,
                "reference_atom_records": reference_atoms,
                "bionexus_sha256": _sha256_text(observed.strip()),
                "reference_sha256": _sha256_text(reference.strip()),
            })
    return {
        "name": "RCSB structure retrieval byte/record concordance",
        "reference": "RCSB PDB download endpoint",
        "passed": all_pass,
        "case_count": len(cases),
        "cases": cases,
        "scope_note": "This validates identifier/retrieval integrity, not structural preparation or biological correctness.",
    }


async def run_ebi_blast() -> dict:
    tool = BlastTool()
    observed = await tool.run_uncached({
        "sequence": HBB_SEQUENCE,
        "program": "blastp",
        "database": "uniprotkb_swissprot",
        "max_hits": 5,
    })
    error = observed.get("error")
    hits = observed.get("hits") or []
    accessions = [str(h.get("accession") or "") for h in hits]
    max_identity = max((float(h.get("identity_pct") or 0) for h in hits), default=0.0)
    target_present = any(acc == "P68871" or "P68871" in acc for acc in accessions)
    passed = error is None and len(hits) > 0 and target_present and max_identity >= 99.0
    return {
        "name": "Live EBI BLAST known-sequence recovery",
        "reference": "EMBL-EBI BLAST against UniProtKB/Swiss-Prot",
        "passed": passed,
        "query": "human hemoglobin beta UniProt P68871 sequence",
        "database": observed.get("database"),
        "source": observed.get("source"),
        "error": error,
        "hit_count": len(hits),
        "top_accessions": accessions,
        "target_accession": "P68871",
        "target_present": target_present,
        "max_identity_pct": max_identity,
        "scope_note": "This is a live service recovery/concordance case. Database releases can change ranking, so the criterion is recovery of the exact target among the first five hits with >=99% identity, not a frozen rank claim.",
    }


async def main(output: Path) -> int:
    result = {
        "suite": "BioNexus Benchmark Suite v1.0 external reference concordance",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "rdkit": rdBase.rdkitVersion,
        },
        "experiments": [],
    }

    result["experiments"].append(run_admet())
    result["experiments"].append(await run_uniprot())
    result["experiments"].append(await run_rcsb())
    result["experiments"].append(await run_ebi_blast())
    result["passed"] = all(exp["passed"] for exp in result["experiments"])

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("../../../benchmark/bbs1/results/reference_concordance.json"))
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.output)))
