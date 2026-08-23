"""CASTp pocket/cavity analysis via Biopython SASA + local detection."""

import asyncio
import logging
import math
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CASTPFOLD_BASE = "https://cfold.bme.uic.edu/castpfold"


async def analyze_pockets_pdb_id(pdb_id: str, probe_radius: float = 1.4) -> dict:
    pdb_text = await _fetch_pdb(pdb_id)
    return await _analyze_pockets(pdb_text, pdb_id, probe_radius)


async def analyze_pockets_pdb_text(pdb_text: str, pdb_id: str = "custom", probe_radius: float = 1.4) -> dict:
    return await _analyze_pockets(pdb_text, pdb_id, probe_radius)


async def _fetch_pdb(pdb_id: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb")
        resp.raise_for_status()
        return resp.text


def _analyze_pockets_sync(pdb_text: str, pdb_id: str, probe_radius: float) -> dict:
    """Compute per-residue SASA and detect pockets via clustering (CPU-bound)."""
    import io
    from Bio.PDB import PDBParser, SASA

    parser = PDBParser(QUIET=True)
    structure = parser.get_structure(pdb_id, io.StringIO(pdb_text))

    sr = SASA.ShrakeRupley()
    sr.compute(structure[0], level="R")

    residues_sasa: list[dict] = []
    coords: list[tuple[float, float, float]] = []

    for chain in structure[0]:
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
            residues_sasa.append({
                "chain": chain.id,
                "residue": residue.resname,
                "resnum": residue.id[1],
                "sasa": round(float(sasa_val), 2),
                "coords": [round(float(c), 3) for c in ca],
            })
            coords.append((float(ca[0]), float(ca[1]), float(ca[2])))

    pockets = _detect_pockets_fast(residues_sasa, coords, probe_radius)

    return {
        "pdb_id": pdb_id,
        "probe_radius": probe_radius,
        "total_residues": len(residues_sasa),
        "pockets": pockets,
        "residues": residues_sasa,
    }


async def _analyze_pockets(pdb_text: str, pdb_id: str, probe_radius: float) -> dict:
    import functools
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, functools.partial(_analyze_pockets_sync, pdb_text, pdb_id, probe_radius)
    )


def _detect_pockets_fast(residues: list[dict], coords: list[tuple], probe_radius: float) -> list[dict]:
    """Detect pockets using scipy KDTree for O(n log n) neighbor lookups."""
    if not residues:
        return []

    exposed = [(i, r) for i, r in enumerate(residues) if r["sasa"] > 1.0]
    if len(exposed) < 5:
        return []

    exposed_coords = [coords[i] for i, _ in exposed]
    n = len(exposed_coords)

    try:
        from scipy.spatial import KDTree
        cutoff = 8.0 + probe_radius * 2
        tree = KDTree(exposed_coords)
        pairs = tree.query_pairs(r=cutoff, output_type='ndarray')

        adj: dict[int, list[int]] = {i: [] for i in range(n)}
        orig_idx = {i: exposed[i][0] for i in range(n)}
        for a, b in pairs:
            adj[a].append(b)
            adj[b].append(a)
    except ImportError:
        adj = _build_adj_brute(exposed_coords, probe_radius)

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
        cluster_residues = [exposed[i][1] for i in cluster_indices]
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


def _build_adj_brute(coords: list[tuple], probe_radius: float) -> dict[int, list[int]]:
    n = len(coords)
    adj: dict[int, list[int]] = {i: [] for i in range(n)}
    cutoff = 8.0 + probe_radius * 2
    for i in range(n):
        for j in range(i + 1, n):
            dx = coords[i][0] - coords[j][0]
            dy = coords[i][1] - coords[j][1]
            dz = coords[i][2] - coords[j][2]
            if dx * dx + dy * dy + dz * dz < cutoff * cutoff:
                adj[i].append(j)
                adj[j].append(i)
    return adj
