"""BBS-2 runnable: drug-likeness rule panel vs literature constants.

Independent ground-truth implementation reads rules.json (literature threshold
constants) + RDKit descriptors and classifies each molecule. BioNexus's
compute_descriptors() output is compared rule-by-rule so any hardcoded
threshold drift in app/tools/admet.py is flagged. Persists a run record and
exits non-zero on any mismatch.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parents[2] / "results" / "cheminformatics" / "drug_likeness"
BACKEND = HERE.parents[3] / "bioai-platform" / "backend"


def base_descriptors(mol):
    return {
        "mw": Descriptors.MolWt(mol),
        "logp": Descriptors.MolLogP(mol),
        "tpsa": Descriptors.TPSA(mol, includeSandP=True),
        "hbd": Lipinski.NumHDonors(mol),
        "hba": rdMolDescriptors.CalcNumLipinskiHBA(mol),
        "rot": Lipinski.NumRotatableBonds(mol),
        "rings": mol.GetRingInfo().NumRings(),
        "heavy": mol.GetNumHeavyAtoms(),
        "hetero": Lipinski.NumHeteroatoms(mol),
        "mr": Descriptors.MolMR(mol),
    }


def classify(name, rules, d):
    verdict = {"lipinski": True, "veber": True, "ghose": True, "egan": True, "muegge": True, "mddr": True}
    reasons = {k: [] for k in verdict}
    lip = rules["filters"]["lipinski"]["thresholds"]
    v = 0
    if d["mw"] > lip["MW_max"]: v += 1
    if d["logp"] > lip["LogP_max"]: v += 1
    if d["hbd"] > lip["HBD_max"]: v += 1
    if d["hba"] > lip["HBA_max"]: v += 1
    verdict["lipinski"] = v <= 1
    if v > 1: reasons["lipinski"].append(f"{v} violations")

    for rule, conds, *rest in [
        ("veber", lambda: d["rot"] <= 10 and d["tpsa"] <= 140),
        ("egan", lambda: d["tpsa"] <= 132 and d["logp"] <= 5.88),
    ]:
        if not conds():
            verdict[rule] = False
            reasons[rule].append("out of published range")

    g = rules["filters"]["ghose"]["thresholds"]
    if g["MW_min"] <= d["mw"] <= g["MW_max"] and g["LogP_min"] <= d["logp"] <= g["LogP_max"] \
       and g["natoms_min"] <= d["heavy"] <= g["natoms_max"] and g["MR_min"] <= d["mr"] <= g["MR_max"]:
        verdict["ghose"] = True
    else:
        verdict["ghose"] = False
        reasons["ghose"].append("out of published range")

    mu = rules["filters"]["muegge"]["thresholds"]
    muegge_ok = (
        mu["MW_min"] <= d["mw"] <= mu["MW_max"]
        and mu["LogP_min"] <= d["logp"] <= mu["LogP_max"]
        and d["tpsa"] <= mu["TPSA_max"]
        and d["rings"] <= mu["rings_max"]
        and d["heavy"] >= mu["heavy_atoms_min"]
        and d["hetero"] >= mu["heteroatoms_min"]
        and d["rot"] <= mu["RotBonds_max"]
        and d["hbd"] <= mu["HBD_max"]
        and d["hba"] <= mu["HBA_max"]
    )
    verdict["muegge"] = muegge_ok
    if not muegge_ok: reasons["muegge"].append("out of published range")

    md = rules["filters"]["mddr"]["thresholds"]
    mddr_ok = (
        md["MW_min"] <= d["mw"] <= md["MW_max"]
        and md["LogP_min"] <= d["logp"] <= md["LogP_max"]
        and d["tpsa"] <= md["TPSA_max"]
        and d["rot"] <= md["RotBonds_max"]
        and d["rings"] <= md["rings_max"]
    )
    verdict["mddr"] = mddr_ok
    if not mddr_ok: reasons["mddr"].append("out of published range")

    return verdict, reasons


def pains(mol):
    patterns = [
        ("Rhodanine", r"[N,n,O,o,S,s]C(=O)CSC(=S)"),
        ("C=CC(=O)", r"C=CC(=O)"),
        ("Quinone", r"C1=CC(=O)C=CC1=O"),
        ("Michael_acceptor", r"C=CC(=O)[N,O]"),
        ("Catechol", r"C1=CC=C(O)C(O)=C1"),
        ("Hydroquinone", r"C1=CC=C(O)C=C1O"),
        ("Aniline", r"Nc1ccccc1"),
        ("Azobenzene", r"N=Nc1ccccc1"),
    ]
    hits = []
    for name, smarts in patterns:
        q = Chem.MolFromSmarts(smarts)
        if q and mol.HasSubstructMatch(q):
            hits.append(name)
    return hits


def brenk(mol):
    from rdkit.Chem import Fragments
    aliases = {"fr_sulfonamide": "fr_sulfonamd", "fr_QuatN": "fr_quatN"}
    fg = lambda n: getattr(Fragments, aliases.get(n, n), lambda m: 0)(mol)
    alerts = []
    if fg("fr_halogen") > 2: alerts.append("Multiple halogen substituents")
    if fg("fr_nitro") > 0: alerts.append("Nitro group (mutagenicity concern)")
    if fg("fr_sulfonamide") > 0: alerts.append("Sulfonamide (hypersensitivity risk)")
    aromatic = sum(1 for ring in mol.GetRingInfo().AtomRings() if all(mol.GetAtomWithIdx(a).GetIsAromatic() for a in ring))
    if aromatic > 5: alerts.append(f"Many aromatic rings ({aromatic})")
    if fg("fr_aldehyde") > 0: alerts.append("Aldehyde (reactive, toxicity concern)")
    if fg("fr_QuatN") > 0: alerts.append("Quaternary nitrogen (P-gp substrate risk)")
    return alerts


def main() -> int:
    rules = json.loads((HERE / "rules.json").read_text(encoding="utf-8"))
    data = json.loads((HERE / "drug_likeness.json").read_text(encoding="utf-8"))

    sys.path.insert(0, str(BACKEND))
    from app.tools.admet import compute_descriptors

    mismatches = []
    spot_check_failures = []
    for entry in data["molecules"]:
        mol = Chem.MolFromSmiles(entry["smiles"])
        if mol is None:
            mismatches.append({"name": entry["name"], "error": "unparseable (fixture bug)"})
            continue
        d = base_descriptors(mol)
        expected, reasons = classify(entry["name"], rules, d)
        expected.update({"pains": pains(mol), "brenk": brenk(mol)})

        live = compute_descriptors(entry["smiles"])
        live_rules = {
            "lipinski": live["drug_likeness"]["lipinski"]["pass"],
            "veber": live["drug_likeness"]["veber"]["pass"],
            "ghose": live["drug_likeness"]["ghose"]["pass"],
            "egan": live["drug_likeness"]["egan"]["pass"],
            "muegge": live["swissadme"]["drug_likeness"]["muegge"]["pass"],
            "mddr": live["drug_likeness"]["mddr"]["pass"],
            "pains-alerts": sorted(live["structural_alerts"]["pains"]["alerts"]),
            "brenk-alerts": sorted(live["structural_alerts"]["brenk"]["alerts"]),
        }
        dom = {"pains-alerts": "pains", "brenk-alerts": "brenk"}

        for rule in ("lipinski", "veber", "ghose", "egan", "muegge", "mddr"):
            if live_rules[rule] != expected[rule]:
                mismatches.append({
                    "molecule": entry["name"], "rule": rule,
                    "expected_from_literature": expected[rule], "bionexus": live_rules[rule],
                    "literature_reason": reasons.get(rule, []),
                })
        for k, litkey in dom.items():
            if live_rules[k] != sorted(expected[litkey]):
                mismatches.append({
                    "molecule": entry["name"], "rule": litkey,
                    "expected_from_literature": sorted(expected[litkey]), "bionexus": live_rules[k],
                })

        for assert_spec in entry.get("expected_asserts", []):
            rule = assert_spec["rule"]
            if rule in ("lipinski", "veber", "ghose", "egan", "muegge", "mddr"):
                expect_val = assert_spec.get("pass")
                live_val = live_rules[rule]
                ok = live_val == expect_val
            else:
                alert = assert_spec.get("alert")
                live_val = live_rules[f"{rule}-alerts"]
                ok = alert in live_val and expect_val is not None
            if not ok:
                spot_check_failures.append({
                    "molecule": entry["name"], "assert": assert_spec.get("note", ""),
                    "expected": assert_spec.get("pass", assert_spec.get("alert")), "bionexus": live_val,
                })

    passed = not mismatches and not spot_check_failures
    run = {
        "schema": "bionexus-benchmark-run/v1",
        "domain": "cheminformatics",
        "benchmark": "drug_likeness_rules",
        "fixture": "drug_likeness_v1",
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "live_environments": {"python": sys.version.split()[0], "rdkit": __import__("rdkit").__version__},
        "n_molecules": len(data["molecules"]),
        "passed": passed,
        "rule_mismatches": mismatches,
        "spot_check_failures": spot_check_failures,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (RESULTS / f"run_{stamp}.json").write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    (RESULTS / "latest.json").write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")

    print(f"drug-likeness rules: {len(data['molecules'])} molecules, mismatches={len(mismatches)} spot_checks_failed={len(spot_check_failures)} => {'PASS' if passed else 'FAIL'}")
    for m in mismatches[:10]:
        print(f"  rule-mismatch {m}")
    for m in spot_check_failures[:10]:
        print(f"  spot-check-fail {m}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())