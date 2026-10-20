#!/usr/bin/env python3
"""Prospective multisite redocking comparison (V2).

Search the top fpocket candidates, dock into each receptor-derived box, and
rank the resulting poses by fixed-coordinate Vinardo score. Crystal-ligand
coordinates are used only after ranking to calculate benchmark RMSD and site
coverage. The V1 result and its pass criteria are never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "bioai-platform" / "backend"))
sys.path.insert(0, str(HERE))
import run_redock_panel as v1

CCD_URL = "https://files.rcsb.org/ligands/download/{}.cif"
METAL_COFAC = {"1GKC": ("A:1450:ZN",)}


def _fetch_ccd(component: str) -> str:
    if re.fullmatch(r"[A-Z0-9]{1,3}", component) is None:
        raise ValueError(f"Invalid CCD component ID: {component!r}")
    url = CCD_URL.format(component)
    errors = []
    for attempt in range(4):
        try:
            response = httpx.get(url, timeout=60, follow_redirects=True)
            response.raise_for_status()
            if "_chem_comp_atom.atom_id" not in response.text:
                raise ValueError("CCD response lacks atom identity table")
            return response.text
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"attempt {attempt + 1}: {type(exc).__name__}: {exc}")
            if attempt < 3:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"RCSB CCD retrieval failed for {component}: " + "; ".join(errors))


def _split_all_copies(pdb_text: str, resname: str, chains: set[str] | None):
    protein, copies = [], {}
    model_seen = False
    for line in pdb_text.splitlines():
        record = line[:6].strip()
        if record == "MODEL":
            if model_seen:
                break
            model_seen = True
            continue
        if record == "ENDMDL":
            break
        if record == "ATOM":
            if len(line) > 16 and line[16] not in (" ", "A"):
                continue
            if chains is not None and line[21:22].strip() not in chains:
                continue
            protein.append(line)
        elif record in ("TER", "END"):
            protein.append(line)
        elif record == "HETATM" and line[17:20].strip() == resname:
            if len(line) > 16 and line[16] not in (" ", "A"):
                continue
            key = (line[21:22], line[22:26], line[26:27])
            copies.setdefault(key, []).append(line)
    return "\n".join(protein) + "\n", [(key, rows) for key, rows in copies.items()]


def _ccd_tables(ccd_text: str):
    from Bio.PDB.MMCIF2Dict import MMCIF2Dict
    import io
    cif = MMCIF2Dict(io.StringIO(ccd_text))
    ids = cif.get("_chem_comp_atom.atom_id", [])
    elements = cif.get("_chem_comp_atom.type_symbol", [])
    charges = cif.get("_chem_comp_atom.charge", [])
    return {str(name): {"element": str(element).upper(),
                        "charge": int(float(charges[i])) if i < len(charges) and charges[i] not in (".", "?") else 0}
            for i, (name, element) in enumerate(zip(ids, elements))}


def _validate_identity(lines: list[str], ccd_text: str, label: str):
    atom_table = _ccd_tables(ccd_text)
    observed = {}
    for line in lines:
        name = line[12:16].strip()
        element = line[76:78].strip().upper() if len(line) >= 78 else ""
        if not name or name in observed:
            raise ValueError(f"{label} contains empty or duplicate atom name {name!r}")
        observed[name] = element
    expected = {name: value["element"] for name, value in atom_table.items()
                if value["element"] not in ("H", "D")}
    actual = {name: element for name, element in observed.items() if element not in ("H", "D")}
    if actual != expected:
        raise ValueError(f"{label} heavy-atom identity mismatch: missing={sorted(expected.keys()-actual.keys())}, "
                         f"extra={sorted(actual.keys()-expected.keys())}, "
                         f"element_mismatches={sorted(k for k in actual.keys() & expected.keys() if actual[k] != expected[k])}")
    return atom_table


def _make_reference_mol(lines: list[str], ccd_text: str):
    from app.benchmarking.ligand_reference import deposited_ligand
    return deposited_ligand(ccd_text, lines)


def _write_ligand_prep(lines: list[str], ccd_text: str, artifact_dir: Path):
    from rdkit import Chem
    reference = _make_reference_mol(lines, ccd_text)
    sdf = Chem.MolToMolBlock(reference) + "\n$$$$\n"
    source = artifact_dir / "ligand-reference.sdf"
    ligand = artifact_dir / "ligand.pdbqt"
    source.write_text(sdf, encoding="utf-8")
    run = subprocess.run(["obabel", str(source), "-O", str(ligand), "--partialcharge", "gasteiger", "-p", "7.4"],
                         capture_output=True, text=True, timeout=120)
    if run.returncode != 0 or not ligand.is_file() or not ligand.stat().st_size:
        raise RuntimeError(f"CCD ligand PDBQT preparation failed: {run.stderr[:1000]}")
    prepared = ligand.read_text(encoding="utf-8")
    return reference, prepared


def _append_selected_cofactors(pdb_text: str, receptor_pdbqt: str, cofactor_ids: tuple[str, ...],
                                artifact_dir: Path) -> tuple[str, list[dict]]:
    """Validate and add explicitly selected CCD cofactors as rigid atoms.

    The curated panel currently selects the catalytic Zn in 1GKC. Protein and
    cofactor preparation remain separate so bond perception cannot bridge the
    metal to protein residues.
    """
    output, audit = [receptor_pdbqt.rstrip()], []
    for selection in cofactor_ids:
        parts = selection.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid cofactor selection {selection!r}; expected chain:residue:component")
        chain, residue, component = parts
        lines = [line for line in pdb_text.splitlines()
                 if line.startswith("HETATM") and line[21:22].strip() == chain
                 and line[22:26].strip() == residue and line[17:20].strip() == component]
        if not lines:
            raise ValueError(f"Selected cofactor {selection} is absent from the deposited structure")
        ccd = _fetch_ccd(component)
        (artifact_dir / f"cofactor-{component}.cif").write_text(ccd, encoding="utf-8")
        atom_table = _validate_identity(lines, ccd, selection)
        if len(lines) != 1:
            raise ValueError(f"Only a CCD-validated single-atom cofactor is currently supported: {selection}")
        line = lines[0]
        atom_name = line[12:16].strip()
        atom = atom_table[atom_name]
        serials = [int(row[6:11]) for row in output[0].splitlines()
                   if row.startswith(("ATOM", "HETATM")) and row[6:11].strip().isdigit()]
        serial = max(serials, default=0) + 1
        x, y, z = (float(line[start:start + 8]) for start in (30, 38, 46))
        # PDBQT stores the CCD formal charge and element-specific AutoDock type.
        charge = atom["charge"]
        record = (f"HETATM{serial:5d} {atom_name:<4s} {component:>3s} {chain}{int(residue):4d}    "
                  f"{x:8.3f}{y:8.3f}{z:8.3f}  0.00  0.00  {charge:8.3f} {atom['element'].title()}")
        output.append(record)
        audit.append({"selection": selection, "ccd_atom_count": len(atom_table),
                      "atom_identity_validated": True, "element": atom["element"],
                      "formal_charge": charge})
    return "\n".join(output) + "\n", audit


def parse_vinardo_score(log: str) -> float:
    """Parse the fixed-pose score emitted by supported Vina versions."""
    match = re.search(r"(?:Estimated Free Energy of Binding|Affinity)\s*:?\s*([-+]?\d+(?:\.\d+)?)", log, re.I)
    if not match:
        raise ValueError("Vinardo score label/value is missing from Vina output")
    return float(match.group(1))


def _search_complete(candidates: list[dict], rows: list[dict], errors: list[dict]) -> bool:
    """Require at least one scored pose from every pocket search.

    Vina's ``--num_modes`` is a maximum. It can return fewer distinct modes
    without an execution failure, so completeness must not require an exact
    pose count per pocket.
    """
    searched = {int(row["pocket_rank"]) for row in rows}
    expected = {int(row["rank"]) for row in candidates}
    return bool(expected) and not errors and expected.issubset(searched)


def _score_vinardo(receptor: Path, pose: str, grid: dict, artifact: Path) -> float:
    from app.tools.docking import _ensure_vina
    with tempfile.TemporaryDirectory(prefix="bionexus-vinardo-") as tmp:
        ligand = Path(tmp) / "pose.pdbqt"
        ligand.write_text(pose, encoding="utf-8")
        score_grid = _pose_scoring_grid(pose, grid)
        command = [_ensure_vina(), "--receptor", str(receptor), "--ligand", str(ligand),
                   "--center_x", str(score_grid["center"][0]), "--center_y", str(score_grid["center"][1]),
                   "--center_z", str(score_grid["center"][2]), "--size_x", str(score_grid["size"][0]),
                   "--size_y", str(score_grid["size"][1]), "--size_z", str(score_grid["size"][2]),
                   "--score_only", "--scoring", "vinardo", "--cpu", "1", "--seed", "42"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired as exc:
            log = (exc.stdout or "") + "\n" + (exc.stderr or "")
            artifact.write_text(json.dumps({"score_grid": score_grid, "log": log}, indent=2), encoding="utf-8")
            raise RuntimeError("Vinardo score-only exceeded 60-second bound") from exc
        log = result.stdout + "\n" + result.stderr
        artifact.write_text(json.dumps({"score_grid": score_grid, "log": log}, indent=2), encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"Vinardo score-only failed: {log[-1000:]}")
        try:
            return parse_vinardo_score(log)
        except ValueError as exc:
            raise RuntimeError(f"Vinardo score not found in output: {log[-1000:]}") from exc


def _pose_scoring_grid(pose: str, minimum_grid: dict, margin: float = 6.0) -> dict:
    """Center score-only grids on the pose and keep receptor context around it."""
    coordinates = []
    for line in pose.splitlines():
        if line.startswith(("ATOM", "HETATM")):
            coordinates.append([float(line[start:start + 8]) for start in (30, 38, 46)])
    if not coordinates:
        raise ValueError("Cannot score a pose without PDBQT atom coordinates")
    lows = [min(point[axis] for point in coordinates) for axis in range(3)]
    highs = [max(point[axis] for point in coordinates) for axis in range(3)]
    center = [(low + high) / 2 for low, high in zip(lows, highs)]
    size = [max(float(minimum_grid["size"][axis]), high - low + 2 * margin)
            for axis, (low, high) in enumerate(zip(lows, highs))]
    return {"center": center, "size": size, "margin_angstrom": margin}


def _ligand_aware_grid(candidate: dict, reference, clearance: float = 8.0,
                       maximum_size: float = 40.0) -> dict:
    """Grow receptor-ranked pocket grids enough to contain the CCD ligand span."""
    conformer = reference.GetConformer()
    coordinates = [conformer.GetAtomPosition(i) for i, atom in enumerate(reference.GetAtoms())
                   if atom.GetAtomicNum() not in (1, 0)]
    if not coordinates:
        raise ValueError("CCD reference has no heavy-atom coordinates")
    spans = [max(getattr(point, axis) for point in coordinates)
             - min(getattr(point, axis) for point in coordinates)
             for axis in ("x", "y", "z")]
    required = [span + clearance for span in spans]
    if any(size > maximum_size for size in required):
        raise ValueError(f"Ligand span requires grid dimensions {required}, exceeding {maximum_size} A")
    size = [round(min(maximum_size, max(float(candidate["size"][axis]), required[axis])), 3)
            for axis in range(3)]
    return {"center": list(candidate["center"]), "size": size,
            "selected_rank": int(candidate["rank"]), "ligand_span_angstrom": spans,
            "required_size_angstrom": required, "maximum_size_angstrom": maximum_size}


def run_case(cx: dict, *, outdir: Path, run_id: str, maximum_pockets: int,
             exhaustiveness: int, chains: set[str] | None) -> dict:
    from rdkit import Chem
    from app.tools.docking import compute_pocket_grid, pdb_to_pdbqt_receptor, run_vina
    from app.benchmarking.docking_redock import symmetry_aware_pose_rmsd

    start = time.monotonic()
    entry = {"id": cx["id"], "pdb": cx["pdb"], "ligand_resname": cx["ligand_resname"],
             "essential": cx["essential"], "method": "multisite-v2",
             "receptor_chains": sorted(chains) if chains else "all",
             "cofactor_selection": list(METAL_COFAC.get(cx["pdb"], ())),
             "search": {"pocket_limit": maximum_pockets, "exhaustiveness": exhaustiveness,
                        "num_modes_per_pocket": 9, "seed": 42,
                        "ranker": "fixed-coordinate Vina 1.2.x Vinardo score-only"}}
    artifact_dir = outdir / "artifacts" / run_id / cx["id"]
    artifact_dir.mkdir(parents=True, exist_ok=True)
    entry["artifact_directory"] = str(artifact_dir.relative_to(outdir))
    try:
        pdb = v1._fetch_pdb(cx["pdb"])
        (artifact_dir / "source.pdb").write_text(pdb, encoding="utf-8")
        protein, copies = _split_all_copies(pdb, cx["ligand_resname"], chains)
        if not copies:
            raise RuntimeError("No deposited ligand copies matched the declared residue name and chain filter")
        component = cx["ligand_resname"]
        ccd_text = _fetch_ccd(component)
        (artifact_dir / "ligand-ccd.cif").write_text(ccd_text, encoding="utf-8")
        ligand_refs = []
        copy_meta = []
        for key, lines in copies:
            _validate_identity(lines, ccd_text, f"ligand copy {key}")
            ligand_refs.append(_make_reference_mol(lines, ccd_text))
            copy_meta.append({"chain": key[0].strip(), "residue_number": key[1].strip(),
                              "insertion_code": key[2].strip(), "heavy_atoms": sum(
                                  1 for line in lines if line[76:78].strip().upper() not in ("H", "D"))})
        entry["ligand_copies"] = copy_meta
        reference, ligand_pdbqt = _write_ligand_prep(copies[0][1], ccd_text, artifact_dir)
        receptor = pdb_to_pdbqt_receptor(protein)
        receptor, cofactor_audit = _append_selected_cofactors(pdb, receptor,
            METAL_COFAC.get(cx["pdb"], ()), artifact_dir)
        (artifact_dir / "receptor.pdbqt").write_text(receptor, encoding="utf-8")
        (artifact_dir / "ligand.pdbqt").write_text(ligand_pdbqt, encoding="utf-8")
        entry["cofactor_preparation"] = cofactor_audit
        candidate_set = compute_pocket_grid(protein)
        if not candidate_set:
            raise RuntimeError("fpocket returned no usable receptor pockets")
        candidates = sorted(candidate_set["candidates"], key=lambda row: int(row["rank"]))[:maximum_pockets]
        entry["fpocket_candidates"] = candidates
        rows, errors = [], []
        for candidate in candidates:
            rank = int(candidate["rank"])
            pocket_dir = artifact_dir / f"pocket-{rank:02d}"
            pocket_dir.mkdir(exist_ok=True)
            try:
                grid = _ligand_aware_grid(candidate, reference)
            except Exception as exc:
                errors.append({"pocket_rank": rank, "error": f"{type(exc).__name__}: {exc}"})
                continue
            (pocket_dir / "grid.json").write_text(json.dumps(grid, indent=2) + "\n", encoding="utf-8")
            try:
                result = run_vina(receptor, ligand_pdbqt, grid_center=grid["center"], grid_size=grid["size"],
                                  exhaustiveness=exhaustiveness, num_modes=9, seed=42)
                models = v1._extract_pdbqt_models(result["result_pdbqt"])
                (pocket_dir / "vina.log").write_text(result["vina_log"], encoding="utf-8")
                (pocket_dir / "poses.pdbqt").write_text(result["result_pdbqt"], encoding="utf-8")
                for model, pose in models.items():
                    try:
                        vinardo = _score_vinardo(artifact_dir / "receptor.pdbqt", pose, grid,
                                                 pocket_dir / f"mode-{model:02d}.vinardo.log")
                        posed = v1._native_pose_molecule(pose, ligand_pdbqt, reference)
                        rmsds = [symmetry_aware_pose_rmsd(ref, posed) for ref in ligand_refs]
                        rows.append({"pocket_rank": rank, "original_model": model,
                                     "vina_affinity": result["poses"][model - 1]["affinity"],
                                     "vinardo_score": vinardo, "rmsd_by_copy": rmsds,
                                     "best_copy_index": int(min(range(len(rmsds)), key=rmsds.__getitem__)),
                                     "top_pose_rmsd_angstrom": min(rmsds), "pose": pose, "grid": grid})
                    except Exception as exc:
                        errors.append({"pocket_rank": rank, "model": model,
                                       "error": f"{type(exc).__name__}: {exc}"})
            except Exception as exc:
                errors.append({"pocket_rank": rank, "error": f"{type(exc).__name__}: {exc}"})
        rows.sort(key=lambda row: (row["vinardo_score"], row["vina_affinity"],
                                  row["pocket_rank"], row["original_model"]))
        for index, row in enumerate(rows, 1):
            row["rank"] = index
        entry["search_complete"] = _search_complete(candidates, rows, errors)
        entry["search_errors"] = errors
        entry["evaluated_pose_count"] = len(rows)
        if not rows:
            raise RuntimeError("No multisite poses were successfully generated and rescored")
        top = rows[0]
        entry["ranked_pose"] = {key: top[key] for key in ("rank", "pocket_rank", "original_model",
                "vina_affinity", "vinardo_score", "rmsd_by_copy", "best_copy_index", "top_pose_rmsd_angstrom")}
        (artifact_dir / "ranked-poses.json").write_text(json.dumps([
            {key: row[key] for key in ("rank", "pocket_rank", "original_model", "vina_affinity",
             "vinardo_score", "rmsd_by_copy", "best_copy_index", "top_pose_rmsd_angstrom")}
            for row in rows], indent=2) + "\n", encoding="utf-8")
        top_pose = top["pose"]
        (artifact_dir / "top-ranked-pose.pdbqt").write_text(top_pose, encoding="utf-8")
        pose_mol = v1._native_pose_molecule(top_pose, ligand_pdbqt, reference)
        (artifact_dir / "top-ranked-pose.sdf").write_text(Chem.MolToMolBlock(pose_mol) + "\n$$$$\n", encoding="utf-8")
        centers = [v1._heavy_centroid(lines) for _, lines in copies]
        pocket_center = top["grid"]["center"]
        offsets = [sum((pocket_center[i] - center[i]) ** 2 for i in range(3)) ** 0.5 for center in centers]
        entry["selected_pocket_site_offsets_angstrom"] = offsets
        entry["site_coverage_passed"] = min(offsets) < 8.0
        entry["pose_recovery_passed"] = top["top_pose_rmsd_angstrom"] < 2.0
        entry["passed"] = entry["search_complete"] and entry["site_coverage_passed"] and entry["pose_recovery_passed"]
        entry["selected_ligand_copy_index"] = top["best_copy_index"]
        entry["vina_version"] = result.get("vina_version", "")
    except Exception as exc:
        entry["passed"] = False
        entry["search_complete"] = False
        entry["error"] = f"{type(exc).__name__}: {exc}"
    entry["runtime_seconds"] = round(time.monotonic() - start, 2)
    entry["artifact_sha256"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in artifact_dir.rglob("*") if path.is_file()}
    return entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=HERE / "redock_panel.json")
    parser.add_argument("--outdir", type=Path, default=REPO / "benchmark/results/docking/multisite-v2")
    parser.add_argument("--pockets", type=int, default=5)
    parser.add_argument("--exhaustiveness", type=int, default=32)
    parser.add_argument("--chains", help="Comma-separated receptor chain IDs; default is all protein chains")
    parser.add_argument("--only", help="Run selected PDB IDs for diagnostics; never labels a partial run as a panel pass")
    args = parser.parse_args()
    if not 1 <= args.pockets <= 10 or not 1 <= args.exhaustiveness <= 128:
        parser.error("--pockets must be 1..10 and --exhaustiveness must be 1..128")
    panel = json.loads(args.panel.read_text(encoding="utf-8"))
    complexes = panel["complexes"]
    if args.only:
        selected = {value.strip().upper() for value in args.only.split(",") if value.strip()}
        complexes = [cx for cx in complexes if cx["pdb"].upper() in selected]
        if len(complexes) != len(selected):
            parser.error("--only contains an unknown or duplicate PDB ID")
    args.outdir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    chains = {value.strip() for value in args.chains.split(",")} if args.chains else None
    criteria = panel["predeclared_success_criteria"]
    fixture_sha = hashlib.sha256(args.panel.read_bytes()).hexdigest()
    method = {"pocket_limit": args.pockets, "exhaustiveness": args.exhaustiveness,
              "num_modes_per_pocket": 9, "seed": 42,
              "pose_ranking": "fixed-coordinate Vinardo score-only on a pose-centered grid with 6 A margin, then Vina affinity, pocket rank, pose index",
              "ligand_copy_policy": "score before evaluation; RMSD against each CCD-validated deposited copy",
              "receptor_chains": sorted(chains) if chains else "all",
              "explicit_cofactors": METAL_COFAC}

    def save_record(results: list[dict], *, finished: bool) -> dict:
        passes = sum(bool(row.get("passed")) for row in results)
        full_panel = finished and len(results) == len(panel["complexes"])
        fraction = passes / len(results) if results else 0.0
        essential = [row for row in results if row.get("essential")]
        panel_passed = full_panel and fraction >= criteria["panel_pass_threshold_frac"] and any(
            row.get("passed") for row in essential)
        record = {"benchmark": "bionexus-redock-panel/v2-multisite", "run_id": run_id,
            "fixture_revision": panel.get("fixture_revision"), "fixture_sha256": fixture_sha,
            "method": method, "executed_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": (("passed" if panel_passed else "failed") if full_panel else
                       ("in_progress" if finished is False else "diagnostic_incomplete_panel")),
            "full_panel": full_panel, "n_complexes": len(results), "n_expected": len(complexes),
            "n_passed": passes, "passed_fraction": round(fraction, 3),
            "success_criteria": criteria, "results": results}
        (args.outdir / "latest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return record

    results = []
    record = save_record(results, finished=False)
    for cx in complexes:
        results.append(run_case(cx, outdir=args.outdir, run_id=run_id, maximum_pockets=args.pockets,
                                exhaustiveness=args.exhaustiveness, chains=chains))
        record = save_record(results, finished=False)
    record = save_record(results, finished=True)
    (args.outdir / f"{run_id}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "status": record["status"], "n_complexes": len(results),
                      "n_passed": record["n_passed"], "result": str(args.outdir / "latest.json")}, indent=2))
    return 0 if record["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
