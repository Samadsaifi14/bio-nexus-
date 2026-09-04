"""BBS-1 external/reference concordance experiment.

Compares BioNexus deterministic/integration outputs with independently queried
reference sources or direct calls to the underlying scientific implementation.
Network-backed cases fail explicitly; unavailable sources are never converted
into passing results.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import primer3
from rdkit import Chem, rdBase
from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors

from app.tools.admet import compute_descriptors
from app.tools.uniprot import UniprotTool
from app.tools.docking import fetch_pdb_from_rcsb
from app.tools.blast import BlastTool
from app.tools.ebi_msa import EBI_TOOLS, run_ebi_msa
from app.routers.primers import PrimerRequest, design_primers

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
HBA_SEQUENCE = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR"
MYOGLOBIN_SEQUENCE = "MGLSDGEWQLVLNVWGKVEADIPGHGQEVLIRLFTGHPETLEKFDKFKHLKSEDEMKASEDLKKHGATVLTALGGILKKKGHHEAELKPLAQSHATKHKIPIKYLEFISEAIIHVLHSRHPGDFGADAQGAMNKALELFRKDIAAKYKELGYQG"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_fasta(text: str) -> dict[str, str]:
    records: dict[str, str] = {}
    name = None
    chunks: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if name is not None:
                records[name] = "".join(chunks)
            name = line[1:].split()[0]
            chunks = []
        elif name is not None:
            chunks.append(line)
    if name is not None:
        records[name] = "".join(chunks)
    return records


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
    cases, all_pass = [], True
    for name, smiles in ADMET_CASES.items():
        observed, reference = compute_descriptors(smiles), _admet_reference(smiles)
        fields, case_pass = {}, True
        for field, expected in reference.items():
            actual = observed.get(field)
            passed = actual == expected
            if isinstance(expected, float) and isinstance(actual, (int, float)):
                passed = abs(float(actual) - expected) <= 1e-12
            fields[field] = {"bionexus": actual, "reference_rdkit": expected, "passed": passed}
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
    tool, cases, all_pass = UniprotTool(), [], True
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
            fields, case_pass = {}, True
            for field, expected_value in expected.items():
                actual = observed.get(field)
                passed = actual == expected_value
                fields[field] = {"bionexus": actual, "reference_uniprot": expected_value, "passed": passed}
                case_pass &= passed
            all_pass &= case_pass
            cases.append({"accession": accession, "passed": case_pass, "fields": fields})
    return {"name": "UniProt field concordance", "reference": "UniProt REST API raw JSON", "passed": all_pass, "case_count": len(cases), "cases": cases}


async def run_rcsb() -> dict:
    cases, all_pass = [], True
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for pdb_id in RCSB_CASES:
            observed = fetch_pdb_from_rcsb(pdb_id)
            response = await client.get(f"https://files.rcsb.org/download/{pdb_id}.pdb")
            response.raise_for_status()
            reference = response.text
            observed_atoms = sum(1 for line in observed.splitlines() if line.startswith(("ATOM  ", "HETATM")))
            reference_atoms = sum(1 for line in reference.splitlines() if line.startswith(("ATOM  ", "HETATM")))
            passed = observed_atoms == reference_atoms and observed_atoms > 0 and _sha256_text(observed.strip()) == _sha256_text(reference.strip())
            all_pass &= passed
            cases.append({"pdb_id": pdb_id, "passed": passed, "bionexus_atom_records": observed_atoms, "reference_atom_records": reference_atoms, "bionexus_sha256": _sha256_text(observed.strip()), "reference_sha256": _sha256_text(reference.strip())})
    return {"name": "RCSB structure retrieval byte/record concordance", "reference": "RCSB PDB download endpoint", "passed": all_pass, "case_count": len(cases), "cases": cases, "scope_note": "This validates identifier/retrieval integrity, not structural preparation or biological correctness."}


async def run_ebi_blast() -> dict:
    observed = await BlastTool().run_uncached({"sequence": HBB_SEQUENCE, "program": "blastp", "database": "uniprotkb_swissprot", "max_hits": 5})
    error, hits = observed.get("error"), observed.get("hits") or []
    accessions = [str(h.get("accession") or "") for h in hits]
    max_identity = max((float(h.get("identity_pct") or 0) for h in hits), default=0.0)
    target_present = any(acc == "P68871" or "P68871" in acc for acc in accessions)
    passed = error is None and len(hits) > 0 and target_present and max_identity >= 99.0
    return {"name": "Live EBI BLAST known-sequence recovery", "reference": "EMBL-EBI BLAST against UniProtKB/Swiss-Prot", "passed": passed, "query": "human hemoglobin beta UniProt P68871 sequence", "database": observed.get("database"), "source": observed.get("source"), "error": error, "hit_count": len(hits), "top_accessions": accessions, "target_accession": "P68871", "target_present": target_present, "max_identity_pct": max_identity, "scope_note": "Database releases can change ranking, so the criterion is recovery of the exact target among the first five hits with >=99% identity, not a frozen rank claim."}


def _primer_template() -> str:
    rng = random.Random(20260904)
    return "".join(rng.choice("ACGT") for _ in range(800))


async def run_primer3() -> dict:
    template = _primer_template()
    req = PrimerRequest(sequence=template, product_size_min=120, product_size_max=260, opt_tm=60.0, num_return=3, gc_min=35.0, gc_max=70.0)
    observed_models = await design_primers(req)
    observed = [m.model_dump() for m in observed_models]
    seq_args = {"SEQUENCE_ID": "target", "SEQUENCE_TEMPLATE": template}
    global_args = {
        "PRIMER_OPT_SIZE": 20, "PRIMER_MIN_SIZE": 18, "PRIMER_MAX_SIZE": 25,
        "PRIMER_OPT_TM": 60.0, "PRIMER_MIN_TM": 57.0, "PRIMER_MAX_TM": 63.0,
        "PRIMER_MIN_GC": 35.0, "PRIMER_MAX_GC": 70.0,
        "PRIMER_PRODUCT_SIZE_RANGE": [[120, 260]], "PRIMER_NUM_RETURN": 3,
        "PRIMER_EXPLAIN_FLAG": 1,
    }
    raw = primer3.bindings.design_primers(seq_args, global_args)
    expected = []
    for i in range(raw.get("PRIMER_PAIR_NUM_RETURNED", 0)):
        lp, rp = raw.get(f"PRIMER_LEFT_{i}"), raw.get(f"PRIMER_RIGHT_{i}")
        if not lp or not rp:
            continue
        expected.append({
            "pair_index": i,
            "left_seq": raw.get(f"PRIMER_LEFT_{i}_SEQUENCE", ""), "left_tm": raw.get(f"PRIMER_LEFT_{i}_TM", 0), "left_gc": raw.get(f"PRIMER_LEFT_{i}_GC_PERCENT", 0), "left_pos": lp[0], "left_len": lp[1],
            "right_seq": raw.get(f"PRIMER_RIGHT_{i}_SEQUENCE", ""), "right_tm": raw.get(f"PRIMER_RIGHT_{i}_TM", 0), "right_gc": raw.get(f"PRIMER_RIGHT_{i}_GC_PERCENT", 0), "right_pos": rp[0], "right_len": rp[1],
            "product_size": raw.get(f"PRIMER_PAIR_{i}_PRODUCT_SIZE", 0), "penalty": raw.get(f"PRIMER_PAIR_{i}_PENALTY", 0),
        })
    passed = len(observed) == len(expected) and len(observed) > 0
    comparisons = []
    for o, e in zip(observed, expected):
        fields = {}
        for key in e:
            ov, ev = o.get(key), e[key]
            same = ov == ev
            if isinstance(ev, float) and isinstance(ov, (int, float)):
                same = abs(float(ov) - ev) <= 1e-9
            fields[key] = {"bionexus": ov, "reference_primer3": ev, "passed": same}
            passed &= same
        comparisons.append({"pair_index": e["pair_index"], "fields": fields})
    return {"name": "Primer3 integration parity", "reference": f"direct primer3-py {getattr(primer3, '__version__', 'unknown')} call", "passed": passed, "returned_pairs": len(observed), "template_length": len(template), "template_sha256": _sha256_text(template), "comparisons": comparisons, "scope_note": "This validates that BioNexus preserves Primer3 outputs for a fixed template and parameter set; it does not establish universal primer specificity or wet-lab performance."}


async def _direct_ebi_msa(base_url: str, fasta: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        submit = await client.post(f"{base_url}/run", data={"email": "bioflow@example.com", "stype": "protein", "sequence": fasta}, headers={"Accept": "text/plain"})
        submit.raise_for_status()
        job_id = submit.text.strip()
        for _ in range(60):
            await asyncio.sleep(1)
            status = (await client.get(f"{base_url}/status/{job_id}")).text.strip()
            if status == "FINISHED":
                break
            if status in ("ERROR", "FAILURE", "FAILED"):
                raise RuntimeError(f"direct EBI MSA failed: {status}")
        else:
            raise TimeoutError("direct EBI MSA timed out")
        result = await client.get(f"{base_url}/result/{job_id}/fa", headers={"Accept": "text/plain"})
        result.raise_for_status()
        return result.text


async def run_msa() -> dict:
    fasta = f">HBB_P68871\n{HBB_SEQUENCE}\n>HBA_P69905\n{HBA_SEQUENCE}\n>MYOGLOBIN\n{MYOGLOBIN_SEQUENCE}\n"
    base = EBI_TOOLS["clustalo"]
    observed = await run_ebi_msa(base_url=base, sequence=fasta, stype="protein", email="bioflow@example.com")
    reference_text = await _direct_ebi_msa(base, fasta)
    observed_records, reference_records = _parse_fasta(observed["aln_fasta"]), _parse_fasta(reference_text)
    passed = observed_records == reference_records and set(observed_records) == {"HBB_P68871", "HBA_P69905", "MYOGLOBIN"}
    alignment_lengths = {k: len(v) for k, v in observed_records.items()}
    return {"name": "Clustal Omega MSA integration parity", "reference": "independent EMBL-EBI Clustal Omega REST job", "passed": passed, "sequence_count": 3, "alignment_lengths": alignment_lengths, "observed_alignment_sha256": _sha256_text(json.dumps(observed_records, sort_keys=True)), "reference_alignment_sha256": _sha256_text(json.dumps(reference_records, sort_keys=True)), "scope_note": "Parity is defined on parsed aligned sequences from two independent EBI jobs using identical inputs. It does not claim one MSA algorithm is biologically superior to another."}


async def main(output: Path) -> int:
    result = {
        "suite": "BioNexus Benchmark Suite v1.0 external reference concordance",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": sys.version, "platform": platform.platform(), "rdkit": rdBase.rdkitVersion, "primer3_py": getattr(primer3, "__version__", "unknown")},
        "experiments": [],
    }
    result["experiments"].append(run_admet())
    result["experiments"].append(await run_uniprot())
    result["experiments"].append(await run_rcsb())
    result["experiments"].append(await run_ebi_blast())
    result["experiments"].append(await run_primer3())
    result["experiments"].append(await run_msa())
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
