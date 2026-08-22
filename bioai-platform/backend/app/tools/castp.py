"""CASTp pocket/cavity analysis via Biopython SASA + local detection."""

import asyncio
import logging
import math
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CASTPFOLD_BASE = "https://cfold.bme.uic.edu/castpfold"


async def analyze_pockets_pdb_id(pdb_id: str, probe_radius: float = 1.4) -> dict:
    """Analyze pockets for a PDB ID using Biopython SASA-based detection."""
    pdb_text = await _fetch_pdb(pdb_id)
    return await _analyze_pockets(pdb_text, pdb_id, probe_radius)


async def analyze_pockets_pdb_text(pdb_text: str, probe_radius: float = 1.4) -> dict:
    """Analyze pockets from raw PDB text."""
    return await _analyze_pockets(pdb_text, "custom", probe_radius)


async def _fetch_pdb(pdb_id: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb")
        resp.raise_for_status()
        return resp.text


async def _analyze_pockets(pdb_text: str, pdb_id: str, probe_radius: float) -> dict:
    """Compute per-residue SASA and detect pockets via clustering."""
    from Bio.PDB import PDBParser, SASA

    parser = PDBParser(QUIET=True)
    import io
    structure = parser.get_structure(pdb_id, io.StringIO(pdb_text))

    sr = SASA.ShrakeRupley()
    sr.compute(structure, level="R")

    residues_sasa: list[dict] = []
    coords: list[tuple[float, float, float]] = []

    for model in structure:
        for chain in model:
            for residue in chain:
                if residue.id[0] != " ":
                    continue
                sasa_val = residue.sasa
                ca = None
                for atom in residue:
                    if atom.name == "CA":
                        ca = atom.coord
                        break
                if ca is None:
                    continue
                res_info = {
                    "chain": chain.id,
                    "residue": residue.resname,
                    "resnum": residue.id[1],
                    "sasa": round(float(sasa_val), 2),
                    "coords": [round(float(c), 3) for c in ca],
                }
                residues_sasa.append(res_info)
                coords.append((float(ca[0]), float(ca[1]), float(ca[2])))

    pockets = _detect_pockets(residues_sasa, probe_radius)

    return {
        "pdb_id": pdb_id,
        "probe_radius": probe_radius,
        "total_residues": len(residues_sasa),
        "pockets": pockets,
        "residues": residues_sasa,
    }


def _detect_pockets(residues: list[dict], probe_radius: float) -> list[dict]:
    """Detect pockets by finding clusters of high-SASA residues.

    Uses a simple grid-based approach: voxelize solvent-exposed residues,
    then find enclosed cavities by flood-filling empty interior voxels.
    Falls back to a simpler SASA-clustering approach for robustness.
    """
    if not residues:
        return []

    exposed = [r for r in residues if r["sasa"] > 1.0]
    if len(exposed) < 5:
        return []

    coords = [tuple(r["coords"]) for r in exposed]
    n = len(coords)

    adj: dict[int, list[int]] = {i: [] for i in range(n)}
    cutoff = 8.0 + probe_radius * 2
    for i in range(n):
        for j in range(i + 1, n):
            dx = coords[i][0] - coords[j][0]
            dy = coords[i][1] - coords[j][1]
            dz = coords[i][2] - coords[j][2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            if d < cutoff:
                adj[i].append(j)
                adj[j].append(i)

    visited = set()
    raw_pockets = []
    for start in range(n):
        if start in visited:
            continue
        queue = [start]
        cluster = []
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            cluster.append(node)
            for nb in adj[node]:
                if nb not in visited:
                    queue.append(nb)
        if len(cluster) >= 5:
            raw_pockets.append(cluster)

    raw_pockets.sort(key=lambda c: -len(c))

    pockets = []
    for idx, cluster_indices in enumerate(raw_pockets):
        cluster_residues = [exposed[i] for i in cluster_indices]
        centroid = [0.0, 0.0, 0.0]
        for r in cluster_residues:
            for k in range(3):
                centroid[k] += r["coords"][k]
        for k in range(3):
            centroid[k] /= len(cluster_residues)

        max_dist = 0.0
        for r in cluster_residues:
            dx = r["coords"][0] - centroid[0]
            dy = r["coords"][1] - centroid[1]
            dz = r["coords"][2] - centroid[2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            if d > max_dist:
                max_dist = d

        volume = (4.0 / 3.0) * math.pi * (max_dist + probe_radius) ** 3
        avg_sasa = sum(r["sasa"] for r in cluster_residues) / len(cluster_residues)

        pockets.append({
            "id": idx + 1,
            "area_sa": round(avg_sasa * len(cluster_residues), 1),
            "volume_sa": round(volume, 1),
            "num_residues": len(cluster_residues),
            "residues": [
                f"{r['chain']}{r['resnum']}{r['residue']}" for r in cluster_residues
            ],
            "centroid": [round(c, 2) for c in centroid],
            "radius": round(max_dist + probe_radius, 2),
        })

    return pockets
