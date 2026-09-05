"""Deterministic docking pose analytics.

Pairwise pose RMSD is atom-order RMSD in the common receptor coordinate frame.
It is intentionally labelled non-symmetry-corrected; chemically symmetric
ligands require an atom-mapping-aware RMSD method for benchmark claims.
"""
from __future__ import annotations

import math
from typing import Any

POLAR = {"N", "O", "S"}
WATER_NAMES = {"HOH", "WAT", "H2O"}


def _xyz(line: str) -> tuple[float, float, float] | None:
    try:
        return float(line[30:38]), float(line[38:46]), float(line[46:54])
    except (ValueError, IndexError):
        parts = line.split()
        try:
            return float(parts[6]), float(parts[7]), float(parts[8])
        except (ValueError, IndexError):
            return None


def _element(line: str) -> str:
    if len(line) >= 78 and line[76:78].strip():
        return line[76:78].strip().upper()
    parts = line.split()
    atom = parts[2] if len(parts) > 2 else ""
    letters = "".join(c for c in atom if c.isalpha())
    return letters[:1].upper()


def parse_vina_models(pdbqt: str) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in (pdbqt or "").splitlines():
        if line.startswith("MODEL"):
            parts = line.split()
            current = {"model": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else len(models) + 1, "atoms": []}
        elif line.startswith("ENDMDL"):
            if current is not None:
                models.append(current)
            current = None
        elif current is not None and line.startswith(("ATOM", "HETATM")):
            coord = _xyz(line)
            if coord is not None:
                current["atoms"].append({"coord": coord, "element": _element(line), "line": line})
    if current is not None:
        models.append(current)
    return models


def _rmsd(a: list[dict], b: list[dict]) -> float | None:
    if not a or len(a) != len(b):
        return None
    total = 0.0
    for aa, bb in zip(a, b):
        if aa.get("element") != bb.get("element"):
            return None
        x1, y1, z1 = aa["coord"]
        x2, y2, z2 = bb["coord"]
        total += (x1-x2)**2 + (y1-y2)**2 + (z1-z2)**2
    return math.sqrt(total / len(a))


def pose_rmsd_matrix(pdbqt: str) -> dict:
    models = parse_vina_models(pdbqt)
    matrix: list[list[float | None]] = []
    for left in models:
        row = []
        for right in models:
            value = _rmsd(left["atoms"], right["atoms"])
            row.append(round(value, 4) if value is not None else None)
        matrix.append(row)
    return {
        "models": [m["model"] for m in models],
        "matrix_angstrom": matrix,
        "method": "atom-order coordinate-frame RMSD",
        "symmetry_corrected": False,
        "limitation": "This is not symmetry-corrected ligand RMSD; symmetric atom mappings can require a chemistry-aware benchmark implementation.",
    }


def cluster_poses(pdbqt: str, cutoff_angstrom: float = 2.0) -> dict:
    rmsd = pose_rmsd_matrix(pdbqt)
    models = rmsd["models"]
    matrix = rmsd["matrix_angstrom"]
    parent = list(range(len(models)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            value = matrix[i][j]
            if value is not None and value <= cutoff_angstrom:
                union(i, j)
    groups: dict[int, list[int]] = {}
    for i, model in enumerate(models):
        groups.setdefault(find(i), []).append(model)
    clusters = sorted(groups.values(), key=lambda x: (-len(x), x[0]))
    return {
        "cutoff_angstrom": cutoff_angstrom,
        "cluster_count": len(clusters),
        "clusters": [{"cluster": i + 1, "models": members, "size": len(members)} for i, members in enumerate(clusters)],
        "clustering": "single-linkage on atom-order pose RMSD",
        "rmsd": rmsd,
    }


def _protein_and_waters(pdb_text: str) -> tuple[list[dict], list[dict]]:
    protein: list[dict] = []
    waters: list[dict] = []
    for line in (pdb_text or "").splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        coord = _xyz(line)
        if coord is None:
            continue
        resname = line[17:20].strip().upper() if len(line) >= 20 else ""
        element = _element(line)
        item = {"coord": coord, "element": element, "resname": resname, "chain": line[21:22].strip(), "resnum": line[22:26].strip(), "atom": line[12:16].strip()}
        if resname in WATER_NAMES and element == "O":
            waters.append(item)
        elif line.startswith("ATOM") and element in POLAR:
            protein.append(item)
    return protein, waters


def _distance(a, b) -> float:
    return math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))


def water_mediated_interactions(pdb_text: str, ligand_pdbqt: str, cutoff_angstrom: float = 3.5) -> dict:
    models = parse_vina_models(ligand_pdbqt)
    if not models:
        return {"status": "UNAVAILABLE", "reason": "No Vina ligand model supplied", "bridges": []}
    protein, waters = _protein_and_waters(pdb_text)
    if not waters:
        return {"status": "NOT_OBSERVED", "water_count": 0, "bridge_count": 0, "bridges": [], "method": "distance-based crystallographic-water bridge screen"}
    ligand = [a for a in models[0]["atoms"] if a.get("element") in POLAR]
    bridges = []
    for w_idx, water in enumerate(waters, 1):
        lig_hits = [(i, _distance(water["coord"], atom["coord"])) for i, atom in enumerate(ligand) if _distance(water["coord"], atom["coord"]) <= cutoff_angstrom]
        if not lig_hits:
            continue
        prot_hits = [(atom, _distance(water["coord"], atom["coord"])) for atom in protein if _distance(water["coord"], atom["coord"]) <= cutoff_angstrom]
        for lig_idx, lig_d in lig_hits:
            for atom, prot_d in prot_hits:
                bridges.append({
                    "water": w_idx,
                    "ligand_polar_atom_index": lig_idx + 1,
                    "protein": f"{atom['chain']}:{atom['resname']}{atom['resnum']}:{atom['atom']}",
                    "water_ligand_distance_angstrom": round(lig_d, 3),
                    "water_protein_distance_angstrom": round(prot_d, 3),
                })
    return {
        "status": "OBSERVED" if bridges else "NOT_OBSERVED",
        "water_count": len(waters),
        "bridge_count": len(bridges),
        "bridges": bridges,
        "cutoff_angstrom": cutoff_angstrom,
        "method": "distance-based crystallographic-water bridge screen",
        "evidence_class": "Heuristic",
        "limitation": "Geometry alone does not establish hydrogen-bond energetics or water occupancy; protonation and explicit solvent treatment are not inferred.",
    }
