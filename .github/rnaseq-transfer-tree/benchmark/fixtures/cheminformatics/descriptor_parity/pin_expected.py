"""Pin the expected descriptor values for the descriptor-parity fixture.

Writes expected_descriptors.json recording:
  * the RDKit version used (rdkit 2022.09.5 in the current env),
  * exact descriptor outputs for every parseable molecule,
  * declared parse-failure expectations for intentionally hard inputs.

This is a REFERENCE pin, not a benchmark result. The parity verdict is produced
by run_descriptor_parity.py and stored under ../../results/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors
from rdkit.Chem.rdchem import Mol

HERE = Path(__file__).resolve().parent

INT_FIELDS = [
    "HeavyAtomCount", "NumHDonors", "NumHAcceptors", "NumRotatableBonds",
    "NumRings", "NumAromaticRings", "NumAliphaticRings", "NumHeteroRings",
    "NumRadicalElectrons", "FormalCharge", "NumHeteroatoms",
]
FLOAT_FIELDS = [
    "MolWt", "ExactMolWt", "HeavyAtomMolWt", "MolLogP", "TPSA", "FractionCSP3",
]
STRING_FIELDS = ["CanonicalSMILES", "Formula", "InChI", "InChIKey"]


RDMOLS = {
    "NumRotatableBonds": rdMolDescriptors.CalcNumRotatableBonds,
    "NumRings": rdMolDescriptors.CalcNumRings,
    "NumAromaticRings": rdMolDescriptors.CalcNumAromaticRings,
    "NumAliphaticRings": rdMolDescriptors.CalcNumAliphaticRings,
    "NumHeteroatoms": rdMolDescriptors.CalcNumHeteroatoms,
}


def count_num_hetero_rings(mol: Mol) -> int:
    # rings containing at least one atom that is not C or H
    atom_hetero = [a.GetAtomicNum() not in (1, 6) for a in mol.GetAtoms()]
    return sum(
        1
        for ring in mol.GetRingInfo().AtomRings()
        if any(atom_hetero[i] for i in ring)
    )


DESCRIPTOR_FNS = {
    "NumHDonors": Descriptors.NumHDonors,
    "NumHAcceptors": Descriptors.NumHAcceptors,
    "NumRadicalElectrons": Descriptors.NumRadicalElectrons,
    "HeavyAtomCount": Descriptors.HeavyAtomCount,
    "MolWt": Descriptors.MolWt,
    "ExactMolWt": Descriptors.ExactMolWt,
    "HeavyAtomMolWt": Descriptors.HeavyAtomMolWt,
    "MolLogP": Descriptors.MolLogP,
    "FractionCSP3": Descriptors.FractionCSP3,
    "TPSA": rdMolDescriptors.CalcTPSA,
}


def compute(mol: Mol):
    out = {}
    for f in INT_FIELDS:
        if f == "NumHeteroRings":
            out[f] = count_num_hetero_rings(mol)
        elif f == "FormalCharge":
            out[f] = int(Chem.GetFormalCharge(mol))
        else:
            out[f] = int(RDMOLS[f](mol) if f in RDMOLS else DESCRIPTOR_FNS[f](mol))
    for f in FLOAT_FIELDS:
        out[f] = round(float(DESCRIPTOR_FNS[f](mol)), 12)
    out["CanonicalSMILES"] = Chem.MolToSmiles(mol)
    out["Formula"] = rdMolDescriptors.CalcMolFormula(mol)
    out["InChI"] = Chem.MolToInchi(mol)
    out["InChIKey"] = Chem.MolToInchiKey(mol)
    return out


def main() -> int:
    data = json.loads((HERE / "molecules.json").read_text(encoding="utf-8"))
    mols = []
    for entry in data["molecules"]:
        mol = Chem.MolFromSmiles(entry["smiles"])
        expect_parse = entry.get("expect_parse", True)
        record = {
            "name": entry["name"],
            "smiles": entry["smiles"],
            "tags": entry["tags"],
            "expect_parse": expect_parse,
        }
        if mol is None:
            record["parse_ok"] = False
            if expect_parse:
                print(f"WARNING: expected-parseable molecule failed: {entry['name']}")
        else:
            record["parse_ok"] = True
            record["descriptors"] = compute(mol)
        mols.append(record)

    pinned = {
        "schema_version": "1.0",
        "fixture": "diverse_rdkit_parity_v1",
        "rdkit_pin": __import__("rdkit").__version__,
        "descriptor_fields": {"int": INT_FIELDS, "float": FLOAT_FIELDS, "string": STRING_FIELDS},
        "molecules": mols,
        "parse_expectation": f"{sum(m['expect_parse'] for m in mols)}/1000 molecules expected-parseable",
    }
    out = HERE / "expected_descriptors.json"
    out.write_text(json.dumps(pinned, indent=2) + "\n", encoding="utf-8")
    n_ok = sum(1 for m in mols if m["parse_ok"])
    print(f"pinned expected_descriptors.json: {n_ok}/{len(mols)} molecules parsed " f"(rdkit {pinned['rdkit_pin']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())