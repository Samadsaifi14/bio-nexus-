#!/usr/bin/env python3
"""Execute the predeclared BBS1 1STP-biotin redocking benchmark.

This script is deliberately benchmark-only.  It does not alter production
scores and it never converts an execution failure into a PASS.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

from rdkit import Chem, rdBase

from app.benchmarking.docking_redock import canonical_redocking_fixture, evaluate_redocking
from app.tools.docking import (
    _ensure_obabel,
    fetch_pdb_from_rcsb,
    pdb_to_pdbqt_receptor,
    run_vina,
)


OUT = Path("benchmark/real_data/DOCKING_1STP/results")
OUT.mkdir(parents=True, exist_ok=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ligand_centroid(pdb_block: str) -> list[float]:
    coords: list[tuple[float, float, float]] = []
    for line in pdb_block.splitlines():
        if line[:6].strip() not in {"ATOM", "HETATM"}:
            continue
        element = line[76:78].strip().upper()
        atom_name = line[12:16].strip().upper()
        if element == "H" or (not element and atom_name.startswith("H")):
            continue
        try:
            coords.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
        except ValueError:
            continue
    if not coords:
        raise RuntimeError("No heavy-atom coordinates were found in the crystallographic ligand")
    return [round(sum(c[i] for c in coords) / len(coords), 3) for i in range(3)]


def extract_1stp_blocks(pdb_text: str) -> tuple[str, str]:
    receptor: list[str] = []
    ligand: list[str] = []
    for line in pdb_text.splitlines():
        record = line[:6].strip()
        if record == "ATOM":
            receptor.append(line)
        elif record == "HETATM" and line[17:20].strip().upper() == "BTN":
            ligand.append(line)
    if not receptor:
        raise RuntimeError("1STP receptor ATOM records were not found")
    if not ligand:
        raise RuntimeError("1STP BTN crystallographic ligand records were not found")
    receptor.append("END")
    ligand.append("END")
    return "\n".join(receptor) + "\n", "\n".join(ligand) + "\n"


def ligand_pdb_to_pdbqt(pdb_block: str) -> str:
    pdb_path = OUT / "reference_biotin.pdb"
    pdbqt_path = OUT / "reference_biotin.pdbqt"
    pdb_path.write_text(pdb_block, encoding="utf-8")
    cmd = [
        _ensure_obabel(),
        str(pdb_path),
        "-O",
        str(pdbqt_path),
        "-h",
        "--partialcharge",
        "gasteiger",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    (OUT / "openbabel_ligand_stdout.txt").write_text(completed.stdout or "", encoding="utf-8")
    (OUT / "openbabel_ligand_stderr.txt").write_text(completed.stderr or "", encoding="utf-8")
    if completed.returncode != 0 or not pdbqt_path.exists():
        raise RuntimeError(f"Open Babel ligand preparation failed with exit code {completed.returncode}")
    value = pdbqt_path.read_text(encoding="utf-8")
    if not value.strip():
        raise RuntimeError("Open Babel produced an empty ligand PDBQT")
    return value


def mol_from_pdb(block: str, label: str):
    mol = Chem.MolFromPDBBlock(block, removeHs=False, sanitize=False, proximityBonding=True)
    if mol is None:
        raise RuntimeError(f"RDKit could not parse {label} PDB coordinates")
    return mol


def main() -> int:
    fixture = canonical_redocking_fixture()
    summary: dict = {
        "benchmark_id": fixture["fixture_id"],
        "fixture": fixture,
        "status": "EXECUTION_FAILED",
        "passed": False,
        "claim_boundary": fixture["claim_boundary"],
    }
    try:
        pdb_text = fetch_pdb_from_rcsb(fixture["pdb_id"])
        receptor_pdb, ligand_pdb = extract_1stp_blocks(pdb_text)
        center = ligand_centroid(ligand_pdb)
        size = [float(x) for x in fixture["grid_size_angstrom"]]

        ligand_pdbqt = ligand_pdb_to_pdbqt(ligand_pdb)
        receptor_pdbqt = pdb_to_pdbqt_receptor(receptor_pdb)

        result = run_vina(
            receptor_pdbqt,
            ligand_pdbqt,
            grid_center=center,
            grid_size=size,
            exhaustiveness=int(fixture["exhaustiveness"]),
            num_modes=int(fixture["num_modes"]),
            seed=int(fixture["seed"]),
        )
        predicted_pdb = result.get("ligand_pdb") or ""
        if not predicted_pdb.strip():
            raise RuntimeError("Vina returned no best-pose ligand coordinates")

        reference_mol = mol_from_pdb(ligand_pdb, "reference ligand")
        predicted_mol = mol_from_pdb(predicted_pdb, "predicted ligand")
        evaluation = evaluate_redocking(
            reference_mol,
            predicted_mol,
            threshold_angstrom=float(fixture["pose_rmsd_threshold_angstrom"]),
        )

        (OUT / "input_1STP.pdb").write_text(pdb_text, encoding="utf-8")
        (OUT / "receptor_protein_only.pdb").write_text(receptor_pdb, encoding="utf-8")
        (OUT / "receptor.pdbqt").write_text(receptor_pdbqt, encoding="utf-8")
        (OUT / "predicted_best_pose.pdb").write_text(predicted_pdb, encoding="utf-8")
        (OUT / "vina.log").write_text(result.get("vina_log") or "", encoding="utf-8")

        summary.update(
            {
                "status": "PASSED" if evaluation.passed else "FAILED_ACCEPTANCE",
                "passed": bool(evaluation.passed),
                "evaluation": evaluation.to_dict(),
                "grid_center_angstrom": center,
                "grid_size_angstrom": size,
                "vina": {
                    "version": result.get("vina_version"),
                    "best_affinity_kcal_mol": result.get("affinity"),
                    "num_poses": result.get("num_poses"),
                    "meta": result.get("vina_meta"),
                },
                "hashes": {
                    "input_1STP_pdb_sha256": sha256_text(pdb_text),
                    "receptor_pdb_sha256": sha256_text(receptor_pdb),
                    "receptor_pdbqt_sha256": sha256_text(receptor_pdbqt),
                    "ligand_pdb_sha256": sha256_text(ligand_pdb),
                    "ligand_pdbqt_sha256": sha256_text(ligand_pdbqt),
                    "predicted_best_pose_pdb_sha256": sha256_text(predicted_pdb),
                    "vina_log_sha256": sha256_text(result.get("vina_log") or ""),
                },
                "environment": {
                    "python": sys.version,
                    "platform": platform.platform(),
                    "rdkit": rdBase.rdkitVersion,
                    "openbabel": subprocess.run(
                        [_ensure_obabel(), "-V"], capture_output=True, text=True, timeout=30
                    ).stdout.strip(),
                },
            }
        )
    except Exception as exc:
        summary["error_type"] = type(exc).__name__
        summary["error"] = str(exc)

    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    # Execution/parse failures should fail CI. A scientifically valid executed
    # benchmark that misses the predeclared RMSD threshold is retained as a
    # negative result and also fails this acceptance workflow.
    return 0 if summary.get("status") == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
