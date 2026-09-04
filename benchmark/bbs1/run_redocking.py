"""BBS-1 co-crystal redocking experiment using the canonical Vina 1IEP example.

The benchmark downloads PDB 1IEP, isolates chain A and its crystallographic
imatinib (STI A 201), prepares a rigid receptor with the BioNexus receptor-
preparation function, converts the crystal ligand through SDF using the same
BioNexus ligand-prep path used for docking, docks with BioNexus `run_vina`, and
evaluates the best pose against the crystallographic ligand using the existing
symmetry-aware heavy-atom RMSD benchmark.

A result is PASS only when the best-scoring pose RMSD is <= 2.0 Å. Raw Vina
metadata, score, pose count, hashes and RMSD are written to JSON. Failures are
not converted to WARN or PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from rdkit import Chem, rdBase

from app.benchmarking.docking_redock import evaluate_redocking
from app.tools.docking import (
    _sdf_to_pdbqt,
    fetch_pdb_from_rcsb,
    pdb_to_pdbqt_receptor,
    run_vina,
)

PDB_ID = "1IEP"
RECEPTOR_CHAIN = "A"
LIGAND_RESNAME = "STI"
LIGAND_CHAIN = "A"
LIGAND_RESSEQ = 201
GRID_CENTER = [15.190, 53.903, 16.917]
GRID_SIZE = [20.0, 20.0, 20.0]
EXHAUSTIVENESS = 32
SEED = 42
RMSD_THRESHOLD_ANGSTROM = 2.0


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_complex_parts(pdb_text: str) -> tuple[str, str]:
    receptor_lines: list[str] = []
    ligand_lines: list[str] = []
    for line in pdb_text.splitlines():
        if line.startswith("ATOM  ") and line[21].strip() == RECEPTOR_CHAIN:
            receptor_lines.append(line)
        elif line.startswith("HETATM"):
            try:
                resseq = int(line[22:26])
            except ValueError:
                continue
            if (
                line[17:20].strip() == LIGAND_RESNAME
                and line[21].strip() == LIGAND_CHAIN
                and resseq == LIGAND_RESSEQ
            ):
                ligand_lines.append(line)
    if not receptor_lines:
        raise RuntimeError("1IEP chain-A receptor extraction returned no ATOM records")
    if not ligand_lines:
        raise RuntimeError("1IEP STI A 201 extraction returned no HETATM records")
    return "\n".join(receptor_lines + ["END"]) + "\n", "\n".join(ligand_lines + ["END"]) + "\n"


def _obabel_convert(text: str, input_ext: str, output_ext: str, extra: list[str] | None = None) -> str:
    extra = extra or []
    with tempfile.TemporaryDirectory() as tmp:
        inp = Path(tmp) / f"input.{input_ext}"
        out = Path(tmp) / f"output.{output_ext}"
        inp.write_text(text, encoding="utf-8")
        cmd = ["obabel", str(inp), "-O", str(out), *extra]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError(f"Open Babel conversion failed: {proc.stderr[:1200]}")
        content = out.read_text(encoding="utf-8", errors="replace")
        if not content.strip():
            raise RuntimeError("Open Babel conversion produced empty output")
        return content


def _bionexus_sdf_to_pdbqt(sdf_text: str) -> str:
    """Run the same BioNexus SDF->PDBQT preparation used by the product path."""
    with tempfile.NamedTemporaryFile(suffix=".sdf", delete=False, mode="w", encoding="utf-8") as fh:
        fh.write(sdf_text)
        path = fh.name
    try:
        return _sdf_to_pdbqt(path)
    finally:
        if os.path.exists(path):
            os.unlink(path)


def _mol_from_sdf_text(sdf: str) -> Chem.Mol:
    with tempfile.NamedTemporaryFile(suffix=".sdf", delete=False, mode="w", encoding="utf-8") as fh:
        fh.write(sdf)
        path = fh.name
    try:
        supplier = Chem.SDMolSupplier(path, removeHs=False, sanitize=True)
        mol = next((m for m in supplier if m is not None), None)
    finally:
        os.unlink(path)
    if mol is None:
        raise RuntimeError("RDKit could not parse Open Babel SDF")
    return mol


def main(output: Path) -> int:
    complex_pdb = fetch_pdb_from_rcsb(PDB_ID)
    receptor_pdb, crystal_ligand_pdb = _extract_complex_parts(complex_pdb)

    receptor_pdbqt = pdb_to_pdbqt_receptor(receptor_pdb)
    crystal_sdf = _obabel_convert(crystal_ligand_pdb, "pdb", "sdf")
    crystal_ligand_pdbqt = _bionexus_sdf_to_pdbqt(crystal_sdf)

    docked = run_vina(
        protein_pdbqt=receptor_pdbqt,
        ligand_pdbqt=crystal_ligand_pdbqt,
        grid_center=GRID_CENTER,
        grid_size=GRID_SIZE,
        exhaustiveness=EXHAUSTIVENESS,
        num_modes=9,
        seed=SEED,
    )
    best_pose_pdb = docked.get("ligand_pdb") or ""
    if not best_pose_pdb:
        raise RuntimeError("Vina returned no best-pose PDB")

    predicted_sdf = _obabel_convert(best_pose_pdb, "pdb", "sdf")
    crystal_mol = _mol_from_sdf_text(crystal_sdf)
    predicted_mol = _mol_from_sdf_text(predicted_sdf)

    rmsd = evaluate_redocking(crystal_mol, predicted_mol, threshold_angstrom=RMSD_THRESHOLD_ANGSTROM)
    result = {
        "suite": "BBS-1 co-crystal redocking",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"python_platform": platform.platform(), "rdkit": rdBase.rdkitVersion},
        "case": {
            "pdb_id": PDB_ID,
            "receptor_chain": RECEPTOR_CHAIN,
            "ligand_resname": LIGAND_RESNAME,
            "ligand_chain": LIGAND_CHAIN,
            "ligand_resseq": LIGAND_RESSEQ,
            "grid_center_angstrom": GRID_CENTER,
            "grid_size_angstrom": GRID_SIZE,
            "exhaustiveness": EXHAUSTIVENESS,
            "seed": SEED,
            "ligand_preparation": "BioNexus _sdf_to_pdbqt after crystallographic PDB->SDF conversion",
            "vina_version": docked.get("vina_version"),
            "best_affinity_kcal_mol": docked.get("affinity"),
            "num_poses": docked.get("num_poses"),
            "rmsd_angstrom": rmsd.rmsd_angstrom,
            "rmsd_threshold_angstrom": rmsd.threshold_angstrom,
            "heavy_atom_count": rmsd.atom_count,
            "passed": rmsd.passed,
            "receptor_pdb_sha256": sha256(receptor_pdb),
            "crystal_ligand_pdb_sha256": sha256(crystal_ligand_pdb),
            "crystal_ligand_sdf_sha256": sha256(crystal_sdf),
            "best_pose_pdb_sha256": sha256(best_pose_pdb),
            "vina_meta": docked.get("vina_meta"),
        },
        "passed": rmsd.passed,
        "claim_boundary": "This single 1IEP chain-A case measures co-crystal pose recovery under the specified preparation and Vina settings. It is not evidence of universal docking accuracy or affinity prediction accuracy.",
        "reference_note": "PDB 1IEP contains A and B kinase chains with separate STI ligands; this benchmark uses STI A 201, whose coordinates correspond to the canonical Vina example box around chain A.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if rmsd.passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("../../../benchmark/bbs1/results/redocking_1iep.json"))
    args = parser.parse_args()
    raise SystemExit(main(args.output))
