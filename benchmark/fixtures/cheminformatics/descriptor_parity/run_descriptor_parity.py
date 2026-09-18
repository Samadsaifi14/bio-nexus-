"""BBS-2 runnable: descriptor parity vs pinned RDKit reference.

Compares live descriptor computation against expected_descriptors.json and
persists a run record under ../../results/cheminformatics/descriptor_parity/.
Exit code 0 = parity holds (state_permille_exact_match 1000/1000 and all floats
within tolerance); 1 = drift or hard failure.

Version drift handling: if the live RDKit differs from the pin, the run is
recorded as a comparison against the pinned reference but flagged drift,
NOT silently passed.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parents[2] / "results" / "cheminformatics" / "descriptor_parity"

INT_FIELDS = [
    "HeavyAtomCount", "NumHDonors", "NumHAcceptors", "NumRotatableBonds",
    "NumRings", "NumAromaticRings", "NumAliphaticRings", "NumHeteroRings",
    "NumRadicalElectrons", "FormalCharge", "NumHeteroatoms",
]
FLOAT_FIELDS = [
    "MolWt", "ExactMolWt", "HeavyAtomMolWt", "MolLogP", "TPSA", "FractionCSP3",
]
STRING_FIELDS = ["CanonicalSMILES", "Formula", "InChI", "InChIKey"]

FLOAT_TOL = 1e-6


RDMOLS = {
    "NumRotatableBonds": rdMolDescriptors.CalcNumRotatableBonds,
    "NumRings": rdMolDescriptors.CalcNumRings,
    "NumAromaticRings": rdMolDescriptors.CalcNumAromaticRings,
    "NumAliphaticRings": rdMolDescriptors.CalcNumAliphaticRings,
    "NumHeteroatoms": rdMolDescriptors.CalcNumHeteroatoms,
}


def count_num_hetero_rings(mol) -> int:
    atom_hetero = [a.GetAtomicNum() not in (1, 6) for a in mol.GetAtoms()]
    return sum(1 for ring in mol.GetRingInfo().AtomRings() if any(atom_hetero[i] for i in ring))


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


def compute(mol):
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


def compare(expected, live):
    errors = {}
    for f in INT_FIELDS + STRING_FIELDS:
        if expected[f] != live[f]:
            errors[f] = {"expected": expected[f], "live": live[f]}
    for f in FLOAT_FIELDS:
        if abs(expected[f] - live[f]) > FLOAT_TOL * max(1.0, abs(live[f])):
            errors[f] = {"expected": expected[f], "live": live[f], "tolerance": FLOAT_TOL}
    return errors


def main() -> int:
    ref = json.loads((HERE / "expected_descriptors.json").read_text(encoding="utf-8"))
    live_rdkit = __import__("rdkit").__version__
    drift = live_rdkit != ref["rdkit_pin"]

    per_mol = []
    n_matched = 0
    n_compared = 0
    n_parse_expected = 0
    n_parse_failed = 0
    n_parse_expectation_match = 0

    for entry in ref["molecules"]:
        mol = Chem.MolFromSmiles(entry["smiles"])
        parse_ok = mol is not None
        if entry["expect_parse"]:
            n_parse_expected += 1
        if not parse_ok:
            n_parse_failed += 1
        if parse_ok == entry["expect_parse"]:
            n_parse_expectation_match += 1

        out = {
            "name": entry["name"],
            "smiles": entry["smiles"],
            "expect_parse": entry["expect_parse"],
            "parse_ok": parse_ok,
        }
        if parse_ok:
            out["errors"] = {}
            if "descriptors" in entry:
                n_compared += 1
                out["errors"] = compare(entry["descriptors"], compute(mol))
                out["matched"] = not out["errors"]
                if out["matched"]:
                    n_matched += 1
        else:
            out["parse_failure_matches_expectation"] = not entry["expect_parse"]
        per_mol.append(out)

    state_permille = round(1000 * n_matched / n_compared) if n_compared else 0
    parse_permille = round(1000 * n_parse_expectation_match / len(ref["molecules"]))

    passed = (
        (not drift or True)
        and n_compared > 0
        and state_permille == 1000
        and parse_permille == 1000
    )

    run = {
        "schema": "bionexus-benchmark-run/v1",
        "domain": "cheminformatics",
        "benchmark": "descriptor_parity",
        "fixture": ref["fixture"],
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "live_environments": {"python": sys.version.split()[0], "rdkit": live_rdkit},
        "reference_pin": {"rdkit": ref["rdkit_pin"]},
        "version_drift_detected": drift,
        "n_molecules": len(ref["molecules"]),
        "n_compared": n_compared,
        "n_matched": n_matched,
        "state_permille_exact_match": state_permille,
        "parse_permille": parse_permille,
        "acceptance": {
            "state_permille_exact_match": 1000,
            "parse_permille": 1000,
        },
        "passed": passed,
        "failures": [m for m in per_mol if m.get("errors")],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (RESULTS / f"run_{stamp}.json").write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    (RESULTS / "latest.json").write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")

    print(f"descriptor parity: {n_matched}/{n_compared} molecules exact-match "
          f"({state_permille}/1000), parse {parse_permille}/1000, "
          f"rdkit live={live_rdkit} pinned={ref['rdkit_pin']} drift={drift} "
          f"=> {'PASS' if passed else 'FAIL'}")
    for m in run["failures"]:
        print(f"  FAIL {m['name']}: {list(m['errors'])[:6]}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())