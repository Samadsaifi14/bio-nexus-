"""Canonical BBS-1 redocking benchmark: dock biotin into streptavidin (PDB 1STP).

The runner uses a chemistry-aware, symmetry-aware RDKit RMSD after converting
both the crystal reference ligand and each Vina pose through Open Babel. It also
writes a retained JSON evidence artifact. A configured fixture alone is never a
passed validation result.

Run inside the API image:

    docker run --rm -v <host_dir>:/data bio-nexus-api:bookworm python /data/redock_benchmark.py
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

import httpx

sys.path.insert(0, "/app")

from app.benchmarking.docking_redock import (
    canonical_redocking_fixture,
    evaluate_redocking,
    mol_from_sdf_block,
)
from app.tools.docking import compute_pocket_grid, run_vina

_FIXTURE = canonical_redocking_fixture()
PDB_ID = _FIXTURE["pdb_id"]
LIG_RESNAME = _FIXTURE["ligand_resname"]
RMSD_THRESHOLD = float(_FIXTURE["pose_rmsd_threshold_angstrom"])
SEED = int(_FIXTURE["seed"])
EXHAUSTIVENESS = int(_FIXTURE["exhaustiveness"])
RCSB_DOWNLOAD_BASE = "https://files.rcsb.org/download"
REPORT_PATH = os.environ.get("BIONEXUS_REDOCK_REPORT", "bbs1_redock_1stp_report.json")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _obabel_version() -> str:
    result = subprocess.run(["obabel", "-V"], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return "unknown"
    return (result.stdout or result.stderr).strip()


def fetch_rcsb_pdb(pdb_id: str) -> str:
    """Fetch a PDB only from the fixed HTTPS RCSB download origin."""
    normalized = pdb_id.strip().upper()
    if re.fullmatch(r"[0-9][A-Z0-9]{3}", normalized) is None:
        raise ValueError(f"invalid PDB identifier: {pdb_id!r}")
    response = httpx.get(
        f"{RCSB_DOWNLOAD_BASE}/{normalized}.pdb",
        timeout=60.0,
        follow_redirects=False,
    )
    response.raise_for_status()
    return response.text


def _convert_file_to_sdf(input_path: str, output_path: str) -> str:
    result = subprocess.run(
        ["obabel", input_path, "-O", output_path],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0 or not os.path.isfile(output_path):
        raise RuntimeError(f"Open Babel SDF conversion failed: {result.stderr[:500]}")
    with open(output_path) as handle:
        sdf = handle.read()
    if not sdf.strip():
        raise RuntimeError("Open Babel SDF conversion produced empty output")
    return sdf


def _pose_blocks(output_pdbqt: str) -> dict[int, str]:
    models: dict[int, list[str]] = {}
    current: int | None = None
    for line in output_pdbqt.splitlines():
        if line.startswith("MODEL"):
            parts = line.split()
            if len(parts) < 2:
                continue
            current = int(parts[1])
            models[current] = [line]
            continue
        if current is not None:
            models[current].append(line)
            if line.startswith("ENDMDL"):
                current = None
    return {model: "\n".join(lines) + "\n" for model, lines in models.items()}


def _write_report(report: dict) -> None:
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main() -> int:
    t0 = time.time()
    pdb_text = fetch_rcsb_pdb(PDB_ID)

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
        elif rec == "HETATM" and len(line) >= 20 and line[17:20].strip() == LIG_RESNAME:
            if not (len(line) > 16 and line[16] not in (" ", "A")):
                ref_lines.append(line)

    assert prot_lines and ref_lines, "failed to split receptor/ligand"
    receptor_pdb = "\n".join(prot_lines)
    print(f"[0] fixture={_FIXTURE['fixture_id']} status={_FIXTURE['status']}")
    print(f"[1] {PDB_ID}: {len(prot_lines)} receptor lines, {len(ref_lines)} ligand atom records")

    grid = compute_pocket_grid(receptor_pdb)
    assert grid, "fpocket found no usable pocket"
    heavy_ref = [line for line in ref_lines if not line[12:16].strip().upper().startswith("H")]
    coords = [(float(line[30:38]), float(line[38:46]), float(line[46:54])) for line in heavy_ref]
    cx = sum(c[0] for c in coords) / len(coords)
    cy = sum(c[1] for c in coords) / len(coords)
    cz = sum(c[2] for c in coords) / len(coords)
    site_off = ((grid["center"][0] - cx) ** 2 + (grid["center"][1] - cy) ** 2 +
                (grid["center"][2] - cz) ** 2) ** 0.5
    print(f"[2] pocket grid center={grid['center']} size={grid['size']} | offset from crystal site: {site_off:.1f} A")
    assert site_off < 8.0, "pocket grid does not cover the crystal binding site"

    with tempfile.TemporaryDirectory() as tmp:
        lig_pdb = os.path.join(tmp, "reference_ligand.pdb")
        lig_pdbqt_path = os.path.join(tmp, "reference_ligand.pdbqt")
        ref_sdf_path = os.path.join(tmp, "reference_ligand.sdf")
        with open(lig_pdb, "w") as handle:
            handle.write("\n".join(ref_lines) + "\nEND\n")

        conversion = subprocess.run(
            ["obabel", lig_pdb, "-O", lig_pdbqt_path, "--partialcharge", "gasteiger", "-p", "7.4"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert conversion.returncode == 0 and os.path.isfile(lig_pdbqt_path), conversion.stderr[:500]
        with open(lig_pdbqt_path) as ligand_file:
            ligand_pdbqt = ligand_file.read()
        reference_mol = mol_from_sdf_block(_convert_file_to_sdf(lig_pdb, ref_sdf_path))
        print("[3] crystal ligand prepared; chemistry-aware reference molecule parsed")

        result = run_vina(
            protein_pdbqt=receptor_pdb,
            ligand_pdbqt=ligand_pdbqt,
            grid_center=grid["center"],
            grid_size=grid["size"],
            exhaustiveness=EXHAUSTIVENESS,
            num_modes=9,
            seed=SEED,
        )
        print(f"[4] vina done in {time.time()-t0:.0f}s | best affinity {result['affinity']} kcal/mol | poses: {result['num_poses']}")

        affinity_by_model = {pose["model"]: pose.get("affinity") for pose in result.get("poses", [])}
        pose_results = []
        for model, block in sorted(_pose_blocks(result["result_sdf"]).items()):
            pose_pdbqt = os.path.join(tmp, f"pose_{model}.pdbqt")
            pose_sdf = os.path.join(tmp, f"pose_{model}.sdf")
            with open(pose_pdbqt, "w") as handle:
                handle.write(block)
            try:
                predicted_mol = mol_from_sdf_block(_convert_file_to_sdf(pose_pdbqt, pose_sdf))
                evaluated = evaluate_redocking(reference_mol, predicted_mol, RMSD_THRESHOLD)
                entry = {
                    "model": model,
                    "affinity_kcal_mol": affinity_by_model.get(model),
                    **evaluated.to_dict(),
                }
                print(
                    f"    mode {model}: affinity {affinity_by_model.get(model)} kcal/mol | "
                    f"RMSD {evaluated.rmsd_angstrom:.3f} A [{'PASS' if evaluated.passed else 'fail'}]"
                )
            except Exception as exc:
                entry = {
                    "model": model,
                    "affinity_kcal_mol": affinity_by_model.get(model),
                    "rmsd_angstrom": None,
                    "passed": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                print(f"    mode {model}: RMSD unavailable — {entry['error']}")
            pose_results.append(entry)

    top_pose = next((item for item in pose_results if item["model"] == 1), None)
    passed = bool(top_pose and top_pose.get("passed") is True)
    report = {
        "fixture": _FIXTURE,
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "EXECUTED_PASSED" if passed else "EXECUTED_FAILED",
        "top_pose_passed": passed,
        "rmsd_threshold_angstrom": RMSD_THRESHOLD,
        "pdb_sha256": _sha256_text(pdb_text),
        "vina_output_sha256": _sha256_text(result["result_sdf"]),
        "vina_version": result.get("vina_version"),
        "openbabel_version": _obabel_version(),
        "seed": SEED,
        "exhaustiveness": EXHAUSTIVENESS,
        "grid_center": grid["center"],
        "grid_size": grid["size"],
        "site_offset_angstrom": round(site_off, 4),
        "poses": pose_results,
        "claim_boundary": (
            "This artifact supports only this predeclared 1STP-BTN redocking case. "
            "It does not establish docking accuracy across the complete chemical or target input space."
        ),
    }
    _write_report(report)
    print(f"[5] retained benchmark report: {REPORT_PATH}")
    print("=" * 60)
    if passed:
        print(f"REDOCK BENCHMARK PASSED — top pose reproduces crystal (<={RMSD_THRESHOLD:g} A)")
        return 0
    print("REDOCK BENCHMARK FAILED — investigate before trusting pose-recovery claims")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
