"""BBS-1 docking redocking benchmark helpers.

The benchmark compares a predicted ligand pose with the crystallographic
reference using RDKit's symmetry-aware best RMSD. This is intentionally kept
outside the production docking score path: docking affinity and pose RMSD are
separate quantities and must not be conflated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RedockingResult:
    rmsd_angstrom: float
    threshold_angstrom: float
    passed: bool
    atom_count: int
    metric: str = "RDKit GetBestRMS symmetry-aware heavy-atom RMSD"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _remove_hydrogens(mol):
    from rdkit import Chem

    if mol is None:
        raise ValueError("Ligand molecule could not be parsed")
    return Chem.RemoveHs(mol)


def symmetry_aware_pose_rmsd(reference_mol, predicted_mol) -> float:
    """Return symmetry-aware heavy-atom RMSD in angstrom.

    Both molecules must represent the same ligand graph and contain 3D
    coordinates. RDKit's GetBestRMS searches symmetry-equivalent atom maps,
    avoiding inflated RMSD from arbitrary numbering of equivalent atoms.
    """
    from rdkit.Chem import rdMolAlign

    ref = _remove_hydrogens(reference_mol)
    pred = _remove_hydrogens(predicted_mol)
    if ref.GetNumAtoms() != pred.GetNumAtoms():
        raise ValueError(
            f"Reference/predicted heavy-atom counts differ: "
            f"{ref.GetNumAtoms()} != {pred.GetNumAtoms()}"
        )
    if ref.GetNumConformers() == 0 or pred.GetNumConformers() == 0:
        raise ValueError("Both ligands must contain 3D coordinates")
    return float(rdMolAlign.GetBestRMS(pred, ref))


def evaluate_redocking(reference_mol, predicted_mol, threshold_angstrom: float = 2.0) -> RedockingResult:
    if threshold_angstrom <= 0:
        raise ValueError("threshold_angstrom must be > 0")
    rmsd = symmetry_aware_pose_rmsd(reference_mol, predicted_mol)
    atom_count = _remove_hydrogens(reference_mol).GetNumAtoms()
    return RedockingResult(
        rmsd_angstrom=round(rmsd, 4),
        threshold_angstrom=float(threshold_angstrom),
        passed=rmsd <= threshold_angstrom,
        atom_count=atom_count,
    )


def mol_from_sdf_block(block: str):
    from rdkit import Chem

    mol = Chem.MolFromMolBlock(block, removeHs=False, sanitize=True)
    if mol is None:
        raise ValueError("Could not parse SDF/Mol block")
    return mol
