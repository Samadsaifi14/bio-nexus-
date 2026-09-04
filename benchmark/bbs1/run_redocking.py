"""BBS-1 co-crystal redocking experiment using 1IEP/STI chain A.

The benchmark preserves deposited coordinates but obtains the ligand bond-order template
from the RCSB Chemical Component Dictionary.  This avoids treating PDB CONECT records as
a complete chemical representation, which previously caused RDKit valence sanitisation
failure for STI/imatinib.
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

import requests
from rdkit import Chem, rdBase
from rdkit.Chem import AllChem

from app.benchmarking.docking_redock import evaluate_redocking
from app.tools.docking import _sdf_to_pdbqt, fetch_pdb_from_rcsb, pdb_to_pdbqt_receptor, run_vina

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
CCD_SDF_URL = "https://files.rcsb.org/ligands/download/STI_ideal.sdf"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_complex_parts(pdb_text: str) -> tuple[str, str]:
    lines = pdb_text.splitlines()
    receptor_lines: list[str] = []
    ligand_lines: list[str] = []
    ligand_serials: set[int] = set()
    for line in lines:
        if line.startswith("ATOM  ") and line[21].strip() == RECEPTOR_CHAIN:
            receptor_lines.append(line)
        elif line.startswith("HETATM"):
            try:
                resseq = int(line[22:26]); serial = int(line[6:11])
            except ValueError:
                continue
            if line[17:20].strip() == LIGAND_RESNAME and line[21].strip() == LIGAND_CHAIN and resseq == LIGAND_RESSEQ:
                ligand_lines.append(line); ligand_serials.add(serial)
    conect_lines: list[str] = []
    for line in lines:
        if not line.startswith("CONECT"): continue
        try: serials = [int(x) for x in line[6:].split()]
        except ValueError: continue
        if serials and serials[0] in ligand_serials:
            internal = [serials[0], *[x for x in serials[1:] if x in ligand_serials]]
            if len(internal) > 1: conect_lines.append("CONECT" + "".join(f"{x:5d}" for x in internal))
    if not receptor_lines: raise RuntimeError("1IEP chain-A receptor extraction returned no ATOM records")
    if not ligand_lines: raise RuntimeError("1IEP STI A 201 extraction returned no HETATM records")
    receptor = "\n".join(receptor_lines + ["END"]) + "\n"
    ligand = "\n".join(ligand_lines + conect_lines + ["END"]) + "\n"
    return receptor, ligand


def _obabel_convert(text: str, input_ext: str, output_ext: str, extra: list[str] | None = None) -> str:
    extra = extra or []
    with tempfile.TemporaryDirectory() as tmp:
        inp = Path(tmp) / f"input.{input_ext}"; out = Path(tmp) / f"output.{output_ext}"
        inp.write_text(text, encoding="utf-8")
        proc = subprocess.run(["obabel", str(inp), "-O", str(out), *extra], capture_output=True, text=True, timeout=180)
        if proc.returncode != 0 or not out.exists(): raise RuntimeError(f"Open Babel conversion failed: {proc.stderr[:1200]}")
        content = out.read_text(encoding="utf-8", errors="replace")
        if not content.strip(): raise RuntimeError("Open Babel conversion produced empty output")
        return content


def _bionexus_sdf_to_pdbqt(sdf_text: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".sdf", delete=False, mode="w", encoding="utf-8") as fh:
        fh.write(sdf_text); path = fh.name
    try: return _sdf_to_pdbqt(path)
    finally:
        if os.path.exists(path): os.unlink(path)


def _ccd_template() -> Chem.Mol:
    response = requests.get(CCD_SDF_URL, timeout=30)
    response.raise_for_status()
    mol = Chem.MolFromMolBlock(response.text, removeHs=False, sanitize=True)
    if mol is None: raise RuntimeError("RCSB CCD STI template could not be parsed")
    return mol


def _crystal_mol_from_pdb(pdb_block: str, template: Chem.Mol) -> Chem.Mol:
    raw = Chem.MolFromPDBBlock(pdb_block, removeHs=False, sanitize=False, proximityBonding=False)
    if raw is None: raise RuntimeError("RDKit could not parse deposited STI coordinates")
    try:
        assigned = AllChem.AssignBondOrdersFromTemplate(Chem.RemoveHs(template), Chem.RemoveHs(raw))
        Chem.SanitizeMol(assigned)
    except Exception as exc:
        raise RuntimeError(f"Could not assign CCD bond orders to deposited STI coordinates: {exc}") from exc
    return assigned


def _mol_from_sdf_text(sdf: str) -> Chem.Mol:
    mol = Chem.MolFromMolBlock(sdf, removeHs=True, sanitize=True)
    if mol is None: raise RuntimeError("RDKit could not parse predicted ligand SDF for symmetry-aware RMSD")
    return mol


def _mol_to_sdf(mol: Chem.Mol) -> str:
    return Chem.MolToMolBlock(mol) + "\n$$$$\n"


def main(output: Path) -> int:
    complex_pdb = fetch_pdb_from_rcsb(PDB_ID)
    receptor_pdb, crystal_ligand_pdb = _extract_complex_parts(complex_pdb)
    receptor_pdbqt = pdb_to_pdbqt_receptor(receptor_pdb)
    template = _ccd_template()
    crystal_mol = _crystal_mol_from_pdb(crystal_ligand_pdb, template)
    crystal_sdf = _mol_to_sdf(crystal_mol)
    crystal_ligand_pdbqt = _bionexus_sdf_to_pdbqt(crystal_sdf)

    docked = run_vina(protein_pdbqt=receptor_pdbqt, ligand_pdbqt=crystal_ligand_pdbqt,
                      grid_center=GRID_CENTER, grid_size=GRID_SIZE, exhaustiveness=EXHAUSTIVENESS,
                      num_modes=9, seed=SEED)
    best_pose_pdb = docked.get("ligand_pdb") or ""
    if not best_pose_pdb: raise RuntimeError("Vina returned no best-pose PDB")
    predicted_sdf = _obabel_convert(best_pose_pdb, "pdb", "sdf")
    predicted_mol = _mol_from_sdf_text(predicted_sdf)
    rmsd = evaluate_redocking(crystal_mol, predicted_mol, threshold_angstrom=RMSD_THRESHOLD_ANGSTROM)

    result = {
        "suite": "BBS-1 co-crystal redocking", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"python_platform": platform.platform(), "rdkit": rdBase.rdkitVersion},
        "case": {"pdb_id": PDB_ID, "receptor_chain": RECEPTOR_CHAIN,
                 "ligand": f"{LIGAND_RESNAME} {LIGAND_CHAIN} {LIGAND_RESSEQ}",
                 "grid_center_angstrom": GRID_CENTER, "grid_size_angstrom": GRID_SIZE,
                 "exhaustiveness": EXHAUSTIVENESS, "seed": SEED,
                 "ligand_preparation": "deposited coordinates + RCSB CCD STI bond-order template -> BioNexus PDBQT",
                 "ccd_template_url": CCD_SDF_URL, "vina_version": docked.get("vina_version"),
                 "best_affinity_kcal_mol": docked.get("affinity"), "num_poses": docked.get("num_poses"),
                 "rmsd_angstrom": rmsd.rmsd_angstrom, "rmsd_threshold_angstrom": rmsd.threshold_angstrom,
                 "heavy_atom_count": rmsd.atom_count, "passed": rmsd.passed,
                 "receptor_pdb_sha256": sha256(receptor_pdb), "crystal_ligand_pdb_sha256": sha256(crystal_ligand_pdb),
                 "crystal_ligand_sdf_sha256": sha256(crystal_sdf), "best_pose_pdb_sha256": sha256(best_pose_pdb),
                 "vina_meta": docked.get("vina_meta")},
        "passed": rmsd.passed,
        "claim_boundary": "This single 1IEP chain-A case measures co-crystal pose recovery under the specified preparation and Vina settings. It is not evidence of universal docking or affinity-prediction accuracy.",
        "reference_note": "Deposited coordinates are retained while chemical bond orders come from the RCSB Chemical Component Dictionary template for STI."
    }
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0 if rmsd.passed else 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=Path("../../../benchmark/bbs1/results/redocking_1iep.json"))
    args = parser.parse_args(); raise SystemExit(main(args.output))
