#!/usr/bin/env python3
"""Multi-complex redocking panel runner.

Reads benchmark/fixtures/docking/redock_panel.json and, for each curated
co-crystal complex, runs the *same* docking code path the production API uses
(app.tools.docking.run_vina / compute_pocket_grid) to reproduce the crystal
pose. Emits symmetry-aware heavy-atom RMSD per complex and a panel verdict
against the predeclared success criteria.

IMPORTANT — honesty rule: this runner NEVER fabricates results.
* If AutoDock Vina + OpenBabel + fpocket are not available in this environment
  it writes a `requires_external` run record and exits 2. That is an explicit
  not-executed status, never a pass.
* Live PDBs are fetched on demand from the SSRF-safe fixed RCSB origin.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

import httpx

FIXTURE_DIR = Path(__file__).resolve().parent
REPO = FIXTURE_DIR.parents[2]
sys.path.insert(0, str(REPO / "bioai-platform" / "backend"))

RCSB_DOWNLOAD_BASE = "https://files.rcsb.org/download"


def _tools_available() -> tuple[bool, list[str]]:
    missing = []
    if not _vina_bin():
        missing.append("vina")
    for name, label in (("obabel", "obabel"), ("fpocket", "fpocket")):
        if not shutil.which(name):
            missing.append(label)
    return (not missing), missing


def _vina_bin() -> str | None:
    from app.tools import docking as dock
    return dock._get_vina_binary() if hasattr(dock, "_get_vina_binary") else None


def _fetch_pdb(pdb_id: str) -> str:
    normalized = pdb_id.strip().upper()
    if re.fullmatch(r"[0-9][A-Z0-9]{3}", normalized) is None:
        raise ValueError(f"invalid PDB: {pdb_id!r}")
    resp = httpx.get(f"{RCSB_DOWNLOAD_BASE}/{normalized}.pdb", timeout=60.0, follow_redirects=False)
    resp.raise_for_status()
    return resp.text


def _split_ligand_receptor(pdb_text: str, lig_resname: str):
    ref_lines, prot_lines, seen_model = [], [], False
    for line in pdb_text.splitlines():
        rec = line[:6].strip()
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            continue
        if rec == "ENDMDL":
            break
        if rec == "ATOM":
            if len(line) > 16 and line[16] not in (" ", "A"):
                continue
            prot_lines.append(line)
        elif rec in ("TER", "END"):
            prot_lines.append(line)
        elif rec == "HETATM" and len(line) >= 18 and line[17:20].strip() == lig_resname:
            if not (len(line) > 16 and line[16] not in (" ", "A")):
                ref_lines.append(line)
    return "\n".join(prot_lines), ref_lines


def _heavy_centroid(lig_lines) -> list[float]:
    def is_heavy(name: str) -> bool:
        return name.lstrip()[0] != "H"
    coords = [[float(l[30:38]), float(l[38:46]), float(l[46:54])]
              for l in lig_lines if is_heavy(l[12:16])]
    return [sum(c[i] for c in coords) / len(coords) for i in range(3)] if coords else [0.0, 0.0, 0.0]


def _extract_sdf_models(sdf_text: str) -> dict[int, str]:
    """Split a multi-`$$$$`/MODEL SDF into per-model SDF blocks (1-indexed)."""
    from rdkit import Chem
    blocks = {}
    # If MODEL delimiters present, chunk on those; otherwise chunk on $$$$.
    if "MODEL" in sdf_text and "ENDMDL" in sdf_text:
        cur = None
        for line in sdf_text.splitlines():
            if line.startswith("MODEL"):
                cur = int(line.split()[1]); blocks[cur] = []
            elif line.startswith("ENDMDL"):
                cur = None
            elif cur is not None:
                blocks[cur].append(line)
        return {k: "\n".join(v) for k, v in blocks.items()}
    for i, block in enumerate(sdf_text.split("$$$$")):
        b = block.strip()
        if b:
            blocks[i + 1] = b
    return blocks


def _rmsd_vs_crystal(pose_sdf_block: str, ref_mol) -> float | None:
    """Symmetry-aware heavy-atom RMSD between a Vina pose and the crystal ligand.

    Both are RDKit mols with real element/bond information, so
    symmetry_aware_pose_rmsd (RDKit GetBestRMS) relaxes atom numbering and
    handles symmetric groups correctly. Returns None when the pose cannot be
    parsed or heavy-atom counts differ (honest skip, never a fabricated pass).
    """
    from rdkit import Chem
    from app.benchmarking.docking_redock import symmetry_aware_pose_rmsd

    pose = Chem.MolFromMolBlock(pose_sdf_block, removeHs=False, sanitize=True)
    if pose is None:
        return None
    ref_h = Chem.RemoveHs(Chem.Mol(ref_mol))
    pose_h = Chem.RemoveHs(pose)
    if ref_h.GetNumAtoms() != pose_h.GetNumAtoms():
        return None
    try:
        return symmetry_aware_pose_rmsd(Chem.Mol(ref_mol), pose)
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=FIXTURE_DIR / "redock_panel.json")
    parser.add_argument("--outdir", type=Path, default=REPO / "benchmark" / "results" / "docking" / "redock")
    parser.add_argument("--runtime-out", type=Path)
    args = parser.parse_args()

    panel = json.loads(args.panel.read_text(encoding="utf-8"))
    criteria = panel["predeclared_success_criteria"]

    available, missing = _tools_available()
    if not available:
        record = {
            "benchmark": "bionexus-redock-panel/v1",
            "status": "not_executed",
            "reason": "requires_external",
            "missing_tools": missing,
            "panels_planned": len(panel["complexes"]),
            "success_criteria": criteria,
            "recorded": date.today().isoformat(),
        }
        args.outdir.mkdir(parents=True, exist_ok=True)
        path = args.outdir / "latest.json"
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="")
        print("REDOCK PANEL: not executed (requires Vina/OpenBabel/fpocket) -> honest requires_external record")
        return 2

    results = []
    passes = 0
    for cx in panel["complexes"]:
        t0 = time.time()
        entry = {"id": cx["id"], "pdb": cx["pdb"], "ligand_resname": cx["ligand_resname"],
                 "essential": cx["essential"]}
        try:
            from rdkit import Chem
            pdb_text = _fetch_pdb(cx["pdb"])
            receptor_pdb, ref_lines = _split_ligand_receptor(pdb_text, cx["ligand_resname"])
            if not ref_lines or not receptor_pdb.strip():
                raise RuntimeError("no receptor/ligand lines parsed")
            ref_center = _heavy_centroid(ref_lines)

            from app.tools.docking import compute_pocket_grid, run_vina
            grid = compute_pocket_grid(receptor_pdb)
            if not grid:
                raise RuntimeError("fpocket found no pocket")
            offset = sum((grid["center"][i] - ref_center[i]) ** 2 for i in range(3)) ** 0.5
            if offset >= 8.0:
                raise RuntimeError(f"grid does not cover site (offset {offset:.1f} A)")

            with tempfile.TemporaryDirectory() as tmp:
                lig_pdb = os.path.join(tmp, "lig.pdb")
                lig_pdbqt = os.path.join(tmp, "lig.pdbqt")
                ref_sdf = os.path.join(tmp, "lig_ref.sdf")
                Path(lig_pdb).write_text("\n".join(ref_lines) + "\nEND\n", encoding="utf-8")
                # crystal ligand -> PDBQT (prod prep path)
                r = subprocess.run(
                    ["obabel", lig_pdb, "-O", lig_pdbqt, "--partialcharge", "gasteiger", "-p", "7.4"],
                    capture_output=True, text=True, timeout=120)
                if r.returncode != 0:
                    raise RuntimeError(f"obabel pdbqt failed: {r.stderr[:300]}")
                # crystal ligand -> SDF (coords + bonds for the RMSD reference)
                r2 = subprocess.run(
                    ["obabel", lig_pdb, "-O", ref_sdf, "-p", "7.4"],
                    capture_output=True, text=True, timeout=120)
                if r2.returncode != 0 or not os.path.isfile(ref_sdf):
                    raise RuntimeError(f"obabel sdf failed: {r2.stderr[:300]}")
                ligand_pdbqt = Path(lig_pdbqt).read_text(encoding="utf-8")
                ref_mol = Chem.MolFromMolBlock(Path(ref_sdf).read_text(encoding="utf-8"), removeHs=False, sanitize=True)
                if ref_mol is None:
                    raise RuntimeError("could not parse reference ligand SDF")

            result = run_vina(receptor_pdb, ligand_pdbqt, grid_center=grid["center"],
                              grid_size=grid["size"], exhaustiveness=32, num_modes=9, seed=42)

            # Parse each pose as a separate SDF block for RMSD (atom/bond-aware).
            pose_blocks = _extract_sdf_models(result["result_sdf"])
            top_rmsd = None
            if 1 in pose_blocks:
                top_rmsd = _rmsd_vs_crystal(pose_blocks[1], ref_mol)

            entry["runtime_s"] = round(time.time() - t0, 2)
            entry["top_pose_rmsd_angstrom"] = top_rmsd
            entry["n_pose_models"] = len(pose_blocks)
            entry["affinity_kcal_mol"] = result.get("affinity")
            entry["passed"] = top_rmsd is not None and top_rmsd < criteria["per_complex_rmsd_threshold_angstrom"]
            if entry["passed"]:
                passes += 1
        except Exception as exc:  # per-complex failure
            entry["passed"] = False
            entry["error"] = str(exc)
        results.append(entry)

    passed_frac = passes / len(results)
    essential = [e for e in results if e["essential"]]
    essential_pass = any(e["passed"] for e in essential) if essential else False
    panel_ok = (passed_frac >= criteria["panel_pass_threshold_frac"]
                and (not criteria["essential_top_pose_success"] or essential_pass))

    record = {
        "benchmark": "bionexus-redock-panel/v1",
        "status": "passed" if panel_ok else "failed",
        "recorded": date.today().isoformat(),
        "n_complexes": len(results),
        "n_passed": passes,
        "passed_fraction": round(passed_frac, 3),
        "essential_passed": essential_pass,
        "success_criteria": criteria,
        "results": results,
        "limitations": panel["limitations"],
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "latest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="")
    print(f"REDOCK PANEL {record['status']}: {passes}/{len(results)} complexes < 2.0 A RMSD")
    return 0 if panel_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
