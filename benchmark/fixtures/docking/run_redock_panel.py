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
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timezone
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
    try:
        import rdkit
    except ImportError:
        missing.append("rdkit")
    return (not missing), missing


def _vina_bin() -> str | None:
    from app.tools import docking as dock
    try:
        return dock._ensure_vina()
    except (RuntimeError, OSError):
        return None


def _fetch_pdb(pdb_id: str) -> str:
    normalized = pdb_id.strip().upper()
    if re.fullmatch(r"[0-9][A-Z0-9]{3}", normalized) is None:
        raise ValueError(f"invalid PDB: {pdb_id!r}")
    url = f"{RCSB_DOWNLOAD_BASE}/{normalized}.pdb"
    failures = []
    for attempt in range(4):
        try:
            resp = httpx.get(url, timeout=60.0, follow_redirects=True,
                             headers={"User-Agent": "BioNexus-redock-benchmark/1.0"})
            resp.raise_for_status()
            data = resp.text
            if not any(line.startswith(("ATOM  ", "HETATM")) for line in data.splitlines()):
                raise ValueError(f"RCSB response for {normalized} has no coordinate records")
            return data
        except (httpx.HTTPError, ValueError) as exc:
            failures.append(f"attempt {attempt + 1}: {type(exc).__name__}: {exc}")
            if attempt < 3:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"RCSB failed to provide a valid PDB for {normalized} after 4 attempts: "
                       + "; ".join(failures))


def _split_ligand_receptor(pdb_text: str, lig_resname: str):
    ref_lines, prot_lines, seen_model = [], [], False
    ligand_key = None
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
                key = line[21:27]
                if ligand_key is None:
                    ligand_key = key
                if key == ligand_key:
                    ref_lines.append(line)
    return "\n".join(prot_lines), ref_lines


def _heavy_centroid(lig_lines) -> list[float]:
    def is_heavy(name: str) -> bool:
        return name.lstrip()[0] != "H"
    coords = [[float(l[30:38]), float(l[38:46]), float(l[46:54])]
              for l in lig_lines if is_heavy(l[12:16])]
    if not coords:
        raise ValueError("Crystal ligand contains no heavy-atom coordinates")
    if not all(math.isfinite(v) for xyz in coords for v in xyz):
        raise ValueError("Crystal ligand coordinates must be finite")
    return [sum(c[i] for c in coords) / len(coords) for i in range(3)]


def _extract_pdbqt_models(pdbqt_text: str) -> dict[int, str]:
    """Split the native result_pdbqt artifact; SDF is a separate export."""
    blocks = {}
    cur = None
    for line in pdbqt_text.splitlines():
        if line.startswith("MODEL"):
            cur = int(line.split()[1]); blocks[cur] = []
        elif line.startswith("ENDMDL"):
            cur = None
        elif cur is not None:
            blocks[cur].append(line)
    return {k: "\n".join(v) + "\n" for k, v in blocks.items()}


def _native_pose_output(result: dict) -> tuple[str, dict[int, str]]:
    """Read only the native PDBQT contract, never reinterpret an SDF export."""
    native = result.get("result_pdbqt")
    if not isinstance(native, str) or not native.strip():
        raise ValueError("Docking result is missing the native result_pdbqt artifact")
    models = _extract_pdbqt_models(native)
    if 1 not in models:
        raise ValueError("Native docking output has no top model")
    if len(models) != result.get("num_poses"):
        raise ValueError("Native docking model count disagrees with reported num_poses")
    return native, models


def _restore_pose_chemistry(pose_sdf_block: str, ref_mol):
    """Restore the known ligand graph after PDBQT merges nonpolar hydrogens.

    Bond/charge information comes from the prepared ligand reference, never
    from its coordinates. The docked heavy-atom coordinates remain unchanged.
    """
    from rdkit import Chem
    from rdkit.Chem import AllChem

    pose = Chem.MolFromMolBlock(pose_sdf_block, removeHs=False, sanitize=True)
    if pose is None:
        raise ValueError("Could not parse docked pose SDF")
    ref_h = Chem.RemoveHs(Chem.Mol(ref_mol))
    pose_h = Chem.RemoveHs(pose)
    if ref_h.GetNumAtoms() != pose_h.GetNumAtoms():
        raise ValueError("Reference/predicted heavy-atom counts differ")
    restored = AllChem.AssignBondOrdersFromTemplate(ref_h, pose_h)
    for atom in restored.GetAtoms():
        atom.SetNumRadicalElectrons(0)
        atom.SetNoImplicit(False)
    Chem.SanitizeMol(restored)
    return restored



def _native_pose_molecule(pose_pdbqt: str, prepared_pdbqt: str, ref_mol):
    """Transfer native pose coordinates onto the prepared reference graph.

    Vina preserves input atom serials/types. Reference-to-input correspondence
    is established by original heavy-atom coordinates, never by fitting the
    docked pose to the crystal. Ambiguous or incomplete mappings fail closed.
    Open Babel pose SDF bond perception is not used for this metric.
    """
    from rdkit import Chem
    types = {"A": "C", "C": "C", "N": "N", "NA": "N", "NS": "N",
             "O": "O", "OA": "O", "OS": "O", "S": "S", "SA": "S", "P": "P",
             "F": "F", "Cl": "Cl", "Br": "Br", "I": "I", "H": "H", "HD": "H", "HS": "H"}

    def atoms(block):
        result = {}
        for line in block.splitlines():
            if not line.startswith(("ATOM", "HETATM")):
                continue
            serial = int(line[6:11])
            atom_type = line.split()[-1]
            element = types.get(atom_type)
            if element is None or serial in result:
                raise ValueError("Unknown atom type or duplicate native PDBQT serial")
            xyz = tuple(float(line[start:start + 8]) for start in (30, 38, 46))
            if not all(math.isfinite(v) for v in xyz):
                raise ValueError("Nonfinite native PDBQT coordinates")
            if element != "H":
                result[serial] = (element, xyz)
        return result

    prepared, pose = atoms(prepared_pdbqt), atoms(pose_pdbqt)
    ref = Chem.RemoveHs(Chem.Mol(ref_mol))
    if set(prepared) != set(pose) or len(prepared) != ref.GetNumAtoms():
        raise ValueError("Native pose/preparation/reference heavy-atom identities differ")
    reference_coords = ref.GetConformer()
    output = Chem.Conformer(ref.GetNumAtoms())
    used = set()
    for atom in ref.GetAtoms():
        index = atom.GetIdx()
        point = reference_coords.GetAtomPosition(index)
        matches = [serial for serial, (element, xyz) in prepared.items()
                   if element == atom.GetSymbol() and math.dist((point.x, point.y, point.z), xyz) <= 0.01]
        if len(matches) != 1 or matches[0] in used:
            raise ValueError("Ambiguous reference-to-prepared atom correspondence")
        serial = matches[0]
        if pose[serial][0] != atom.GetSymbol():
            raise ValueError("Native pose changed an atom element")
        used.add(serial)
        output.SetAtomPosition(index, pose[serial][1])
    ref.RemoveAllConformers()
    ref.AddConformer(output)
    Chem.SanitizeMol(ref)
    return ref


def _rmsd_vs_crystal(pose_sdf_block: str, ref_mol) -> float:
    """Symmetry-aware heavy-atom RMSD between a Vina pose and the crystal ligand.

    Both are RDKit mols with real element/bond information, so
    symmetry_aware_pose_rmsd (RDKit CalcRMS) relaxes atom numbering and
    handles symmetric groups correctly. Invalid chemistry fails explicitly.
    """
    from app.benchmarking.docking_redock import symmetry_aware_pose_rmsd
    return symmetry_aware_pose_rmsd(ref_mol, _restore_pose_chemistry(pose_sdf_block, ref_mol))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=FIXTURE_DIR / "redock_panel.json")
    parser.add_argument("--outdir", type=Path, default=REPO / "benchmark" / "results" / "docking" / "redock")
    parser.add_argument("--runtime-out", type=Path)
    parser.add_argument("--engine-timeout", type=float, default=900,
                        help="Per-complex native execution budget; does not change scientific thresholds")
    parser.add_argument("--canonical", action="store_true", help="Run only the predeclared 1STP-BTN control")
    args = parser.parse_args()

    panel = json.loads(args.panel.read_text(encoding="utf-8"))
    criteria = panel["predeclared_success_criteria"]
    if args.canonical:
        from app.benchmarking.docking_redock import canonical_redocking_fixture
        fixture = canonical_redocking_fixture()
        panel["complexes"] = [cx for cx in panel["complexes"] if cx["pdb"] == fixture["pdb_id"]
                              and cx["ligand_resname"] == fixture["ligand_resname"]]
        if len(panel["complexes"]) != 1:
            raise ValueError("Canonical control must match exactly one panel entry")
        criteria = {**criteria, "panel_pass_threshold_frac": 1.0,
                    "note": "Canonical 1STP-BTN control: top pose RMSD <= 2.0 A; no panel-wide validation claim."}

    available, missing = _tools_available()
    if not available:
        record = {
            "benchmark": "BBS1-DOCK-1STP-BTN" if args.canonical else "bionexus-redock-panel/v1",
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
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    from rdkit import rdBase
    tool_versions = {"python": sys.version.split()[0], "rdkit": rdBase.rdkitVersion,
                     "openbabel": subprocess.run(["obabel", "-V"], capture_output=True,
                                                 text=True, timeout=30).stdout.strip(),
                     "vina_binary_sha256": hashlib.sha256(Path(_vina_bin()).read_bytes()).hexdigest(),
                     "fpocket_binary_sha256": hashlib.sha256(Path(shutil.which("fpocket")).read_bytes()).hexdigest()}
    for cx in panel["complexes"]:
        t0 = time.time()
        entry = {"id": cx["id"], "pdb": cx["pdb"], "ligand_resname": cx["ligand_resname"],
                 "essential": cx["essential"]}
        try:
            from rdkit import Chem
            pdb_text = _fetch_pdb(cx["pdb"])
            artifact_dir = args.outdir / "artifacts" / run_id / cx["id"]
            artifact_dir.mkdir(parents=True, exist_ok=True)
            entry["artifact_directory"] = str(artifact_dir.relative_to(args.outdir))
            (artifact_dir / "source.pdb").write_text(pdb_text, encoding="utf-8")
            entry["source_url"] = f"{RCSB_DOWNLOAD_BASE}/{cx['pdb']}.pdb"
            entry["observed_hetatm_resnames"] = sorted({
                line[17:20].strip() for line in pdb_text.splitlines()
                if line.startswith("HETATM") and len(line) >= 20
            })
            if cx["ligand_resname"] not in entry["observed_hetatm_resnames"]:
                raise RuntimeError(
                    f"Declared ligand {cx['ligand_resname']} absent from deposited structure; "
                    f"observed {entry['observed_hetatm_resnames']}"
                )
            receptor_pdb, ref_lines = _split_ligand_receptor(pdb_text, cx["ligand_resname"])
            entry["selected_ligand_atom_records"] = len(ref_lines)
            entry["selected_ligand_instance"] = ref_lines[0][21:27] if ref_lines else None
            if not ref_lines or not receptor_pdb.strip():
                raise RuntimeError("no receptor/ligand lines parsed")
            ref_center = _heavy_centroid(ref_lines)

            from app.tools.docking import compute_pocket_grid, pdb_to_pdbqt_receptor, run_vina
            grid = compute_pocket_grid(receptor_pdb)
            if not grid:
                raise RuntimeError("fpocket found no pocket")
            offset = sum((grid["center"][i] - ref_center[i]) ** 2 for i in range(3)) ** 0.5
            entry["grid"] = grid
            entry["site_offset_angstrom"] = offset
            # Keep the declared site gate, but execute docking even when it
            # fails so a failed case still retains native poses and RMSD.
            entry["site_coverage_passed"] = offset < 8.0

            with tempfile.TemporaryDirectory() as tmp:
                lig_pdb = os.path.join(tmp, "lig.pdb")
                lig_pdbqt = os.path.join(tmp, "lig.pdbqt")
                ref_sdf = os.path.join(tmp, "lig_ref.sdf")
                Path(lig_pdb).write_text("\n".join(ref_lines) + "\nEND\n", encoding="utf-8")
                # Validate the reference graph before preparing PDBQT. PDB does
                # not encode bond orders; use official CCD if perception fails.
                r2 = subprocess.run(
                    ["obabel", lig_pdb, "-O", ref_sdf, "-p", "7.4"],
                    capture_output=True, text=True, timeout=120)
                if r2.returncode != 0 or not os.path.isfile(ref_sdf):
                    raise RuntimeError(f"obabel sdf failed: {r2.stderr[:300]}")
                ref_mol = Chem.MolFromMolBlock(Path(ref_sdf).read_text(encoding="utf-8"), removeHs=False, sanitize=True)
                prep_input = lig_pdb
                entry["ligand_chemistry_source"] = "Open Babel PDB bond perception"
                if ref_mol is None:
                    from app.benchmarking.ligand_reference import deposited_ligand
                    component = cx["ligand_resname"]
                    if re.fullmatch(r"[A-Z0-9]{1,3}", component) is None:
                        raise ValueError("Invalid CCD component identifier")
                    url = f"https://files.rcsb.org/ligands/download/{component}.cif"
                    response = httpx.get(url, timeout=60, follow_redirects=False)
                    response.raise_for_status()
                    (artifact_dir / "ligand_ccd.cif").write_text(response.text)
                    ref_mol = deposited_ligand(response.text, ref_lines)
                    Path(ref_sdf).write_text(Chem.MolToMolBlock(ref_mol) + "\n$$$$\n")
                    prep_input = ref_sdf
                    entry["ligand_chemistry_source"] = url
                r = subprocess.run(
                    ["obabel", prep_input, "-O", lig_pdbqt, "--partialcharge", "gasteiger", "-p", "7.4"],
                    capture_output=True, text=True, timeout=120)
                if r.returncode != 0:
                    raise RuntimeError(f"obabel pdbqt failed: {r.stderr[:300]}")
                ligand_pdbqt = Path(lig_pdbqt).read_text(encoding="utf-8")
                for name in ("lig.pdb", "lig.pdbqt", "lig_ref.sdf"):
                    shutil.copyfile(Path(tmp) / name, artifact_dir / name)

            receptor_pdbqt = pdb_to_pdbqt_receptor(receptor_pdb)
            (artifact_dir / "receptor.pdbqt").write_text(receptor_pdbqt, encoding="utf-8")
            result = run_vina(receptor_pdbqt, ligand_pdbqt, grid_center=grid["center"],
                              grid_size=grid["size"], exhaustiveness=32, num_modes=9, seed=42,
                              timeout_seconds=args.engine_timeout)

            native_pdbqt, pose_blocks = _native_pose_output(result)
            (artifact_dir / "vina_output.pdbqt").write_text(native_pdbqt, encoding="utf-8")
            if result.get("result_sdf"):
                (artifact_dir / "vina_output.sdf").write_text(result["result_sdf"], encoding="utf-8")
            (artifact_dir / "vina.log").write_text(result["vina_log"], encoding="utf-8")
            top_rmsd = None
            if 1 in pose_blocks:
                pose_path = artifact_dir / "top_pose.pdbqt"
                sdf_path = artifact_dir / "top_pose.sdf"
                pose_path.write_text(pose_blocks[1], encoding="utf-8")
                conversion = subprocess.run(["obabel", str(pose_path), "-O", str(sdf_path)],
                                            capture_output=True, text=True, timeout=120)
                entry["pose_sdf_export_valid"] = False
                if conversion.returncode != 0 or not sdf_path.is_file():
                    entry["pose_sdf_export_error"] = conversion.stderr[:300]
                else:
                    exported = Chem.MolFromMolBlock(sdf_path.read_text(encoding="utf-8"), sanitize=True)
                    entry["pose_sdf_export_valid"] = exported is not None
                    if exported is None:
                        entry["pose_sdf_export_error"] = "Open Babel pose SDF failed chemical sanitization; retained as failed export evidence"
                from app.benchmarking.docking_redock import symmetry_aware_pose_rmsd
                restored = _native_pose_molecule(pose_blocks[1], ligand_pdbqt, ref_mol)
                top_rmsd = symmetry_aware_pose_rmsd(ref_mol, restored)
                (artifact_dir / "top_pose_chemical_graph.sdf").write_text(
                    Chem.MolToMolBlock(restored) + "\n$$$$\n", encoding="utf-8")

            entry["grid"] = grid
            entry["site_offset_angstrom"] = offset
            entry["vina_version"] = result["vina_version"]
            entry["seed"] = 42
            entry["exhaustiveness"] = 32
            entry["atom_correspondence"] = "prepared PDBQT serials mapped to reference by original heavy-atom coordinates; no pose fitting"
            entry["metric"] = "RDKit CalcRMS symmetry-aware heavy-atom RMSD in receptor frame (no alignment)"
            entry["artifact_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in artifact_dir.iterdir() if p.is_file()}
            entry["runtime_s"] = round(time.time() - t0, 2)
            entry["top_pose_rmsd_angstrom"] = top_rmsd
            entry["n_pose_models"] = len(pose_blocks)
            entry["affinity_kcal_mol"] = result.get("affinity")
            threshold = criteria["per_complex_rmsd_threshold_angstrom"]
            entry["pose_recovery_passed"] = top_rmsd is not None and (top_rmsd <= threshold if args.canonical else top_rmsd < threshold)
            entry["passed"] = entry["site_coverage_passed"] and entry["pose_recovery_passed"]
            if not entry["site_coverage_passed"]:
                entry["error"] = f"grid does not cover site (offset {offset:.1f} A); native docking completed for diagnosis"
            if entry["passed"]:
                passes += 1
        except Exception as exc:  # per-complex failure
            entry["passed"] = False
            entry["error"] = str(exc)
            if isinstance(exc, subprocess.TimeoutExpired) and entry.get("artifact_directory"):
                output = exc.stdout or ""
                if isinstance(output, bytes):
                    output = output.decode("utf-8", errors="replace")
                (args.outdir / entry["artifact_directory"] / "vina_timeout.log").write_text(output)
        artifact_relative = entry.get("artifact_directory")
        if artifact_relative:
            entry["artifact_sha256"] = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (args.outdir / artifact_relative).iterdir() if path.is_file()
            }
        entry["runtime_s"] = round(time.time() - t0, 2)
        results.append(entry)

    passed_frac = passes / len(results)
    essential = [e for e in results if e["essential"]]
    essential_pass = any(e["passed"] for e in essential) if essential else False
    panel_ok = (passed_frac >= criteria["panel_pass_threshold_frac"]
                and (not criteria["essential_top_pose_success"] or essential_pass))

    record = {
        "benchmark": "BBS1-DOCK-1STP-BTN" if args.canonical else "bionexus-redock-panel/v1",
        "run_id": run_id,
        "fixture_revision": panel.get("fixture_revision"),
        "fixture_sha256": hashlib.sha256(args.panel.read_bytes()).hexdigest(),
        "tool_versions": tool_versions,
        "engine_timeout_seconds": args.engine_timeout,
        "code_sha256": {path: hashlib.sha256((REPO / path).read_bytes()).hexdigest() for path in (
            "benchmark/fixtures/docking/run_redock_panel.py",
            "bioai-platform/backend/app/tools/docking.py",
            "bioai-platform/backend/app/benchmarking/docking_redock.py",
            "bioai-platform/backend/app/benchmarking/ligand_reference.py")},
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
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
    (args.outdir / f"{run_id}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("REDOCK_EVIDENCE=" + json.dumps(record, sort_keys=True))
    print(f"REDOCK PANEL {record['status']}: {passes}/{len(results)} complexes < 2.0 A RMSD")
    return 0 if panel_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
