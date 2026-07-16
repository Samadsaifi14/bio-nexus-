"""ADMET descriptor computation using RDKit.

Computes molecular descriptors from SMILES strings:
- Lipinski Rule of Five (pass/fail + violations)
- Veber rules (rotatable bonds, TPSA)
- QED (Quantitative Estimate of Drug-likeness)
- Key properties: MW, LogP, TPSA, HBD, HBA, rotatable bonds
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def compute_descriptors(smiles: str) -> dict:
    """Compute ADMET-relevant molecular descriptors from a SMILES string.

    Returns a dict with all computed properties, Lipinski/Veber compliance,
    and QED score. Raises ValueError on invalid SMILES.
    """
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Lipinski, QED, rdMolDescriptors

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES: {smiles!r}")

    # Core descriptors
    mw = round(Descriptors.MolWt(mol), 2)
    logp = round(Descriptors.MolLogP(mol), 2)
    tpsa = round(Descriptors.TPSA(mol), 2)
    hbd = Lipinski.NumHDonors(mol)
    hba = Lipinski.NumHAcceptors(mol)
    rotatable = Lipinski.NumRotatableBonds(mol)
    qed_score = round(QED.qed(mol), 4)
    heavy_atoms = mol.GetNumHeavyAtoms()
    formula = rdMolDescriptors.CalcMolFormula(mol)

    # Lipinski Rule of Five
    lipinski_violations = []
    if mw > 500:
        lipinski_violations.append(f"Molecular weight {mw} > 500")
    if logp > 5:
        lipinski_violations.append(f"LogP {logp} > 5")
    if hbd > 5:
        lipinski_violations.append(f"H-bond donors {hbd} > 5")
    if hba > 10:
        lipinski_violations.append(f"H-bond acceptors {hba} > 10")
    lipinski_pass = len(lipinski_violations) == 0

    # Veber rules
    veber_violations = []
    if rotatable > 10:
        veber_violations.append(f"Rotatable bonds {rotatable} > 10")
    if tpsa > 140:
        veber_violations.append(f"TPSA {tpsa} > 140")
    veber_pass = len(veber_violations) == 0

    return {
        "smiles": smiles,
        "formula": formula,
        "heavy_atoms": heavy_atoms,
        "molecular_weight": mw,
        "logp": logp,
        "tpsa": tpsa,
        "hbd": hbd,
        "hba": hba,
        "rotatable_bonds": rotatable,
        "qed_score": qed_score,
        "lipinski": {
            "pass": lipinski_pass,
            "violations": lipinski_violations,
            "violation_count": len(lipinski_violations),
        },
        "veber": {
            "pass": veber_pass,
            "violations": veber_violations,
            "violation_count": len(veber_violations),
        },
    }
