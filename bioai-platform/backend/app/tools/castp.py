"""Pocket/cavity analysis — uses fpocket (real tool) with Biopython SASA fallback.

Priority chain:
1. fpocket local binary (installed in Docker) — produces druggability scores,
   volumes, areas, and residue lists per pocket.
2. Biopython ShrakeRupley SASA + KDTree clustering — lightweight fallback
   when fpocket is unavailable.

Both produce the same output contract so callers don't need to change.
"""

import asyncio
import logging
import math
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CASTPFOLD_BASE = "https://cfold.bme.uic.edu/castpfold"
FPOCKET_BIN: str = "/usr/local/bin/fpocket"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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


async def _analyze_pockets(pdb_text: str, pdb_id: str, probe_radius: float) -> dict:
    # 1. Try fpocket (real tool)
    import shutil
    fpocket = FPOCKET_BIN if Path(FPOCKET_BIN).exists() else (shutil.which("fpocket") or "")
    if fpocket and Path(fpocket).exists():
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, _run_fpocket_analysis, fpocket, pdb_text, pdb_id, probe_radius,
        )
        if result["pockets"]:
            _attach_structure_summary(pdb_text, result)
            return result
        logger.info("fpocket found no pockets for %s, falling back to SASA heuristic", pdb_id)

    # 2. Fallback: Biopython SASA + KDTree clustering
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, _analyze_pockets_sasa_sync, pdb_text, pdb_id, probe_radius,
    )
    _attach_structure_summary(pdb_text, result)
    return result


# ---------------------------------------------------------------------------
# fpocket analysis
# ---------------------------------------------------------------------------

def _run_fpocket_analysis(
    fpocket_bin: str,
    pdb_text: str,
    pdb_id: str,
    probe_radius: float,
) -> dict:
    """Run fpocket and parse results into the standard output contract."""
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = Path(tmpdir) / "input.pdb"
        in_path.write_text(pdb_text)

        try:
            subprocess.run(
                [fpocket_bin, "-f", str(in_path), "-r", str(probe_radius)],
                capture_output=True, text=True, timeout=60,
            )
        except subprocess.TimeoutExpired:
            logger.warning("fpocket timed out for %s", pdb_id)
            return _empty_result(pdb_id, probe_radius, 0)
        except Exception as e:
            logger.warning("fpocket failed for %s: %s", pdb_id, e)
            return _empty_result(pdb_id, probe_radius, 0)

        fpocket_out = Path(tmpdir) / "input_out"
        return _parse_fpocket(fpocket_out, pdb_id, probe_radius)


def _parse_fpocket(out_dir: Path, pdb_id: str, probe_radius: float) -> dict:
    """Parse fpocket output into standard pocket list."""
    info_file = out_dir / "info" / "infos.txt"
    if not info_file.exists():
        return _empty_result(pdb_id, probe_radius, 0)

    pockets: list[dict] = []
    current: dict[str, Any] = {}

    try:
        text = info_file.read_text()
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("Pocket"):
                if current:
                    pockets.append(current)
                m = re.search(r"Pocket\s+(\d+)", line)
                current = {
                    "id": int(m.group(1)) if m else len(pockets) + 1,
                    "druggability_score": 0.0,
                    "volume": 0.0,
                    "area_sa": 0.0,
                    "score": 0.0,
                    "num_residues": 0,
                    "centroid": [0.0, 0.0, 0.0],
                    "radius": 0.0,
                }
            elif "Druggability Score" in line:
                m = re.search(r":\s*([\d.]+)", line)
                if m:
                    current["druggability_score"] = float(m.group(1))
            elif "Volume" in line:
                m = re.search(r":\s*([\d.]+)", line)
                if m:
                    current["volume"] = float(m.group(1))
            elif "Area" in line:
                m = re.search(r":\s*([\d.]+)", line)
                if m:
                    current["area_sa"] = float(m.group(1))
            elif "Score" in line and "Drug" not in line:
                m = re.search(r":\s*([\d.]+)", line)
                if m:
                    current["score"] = float(m.group(1))
            elif "Number of residues" in line:
                m = re.search(r":\s*(\d+)", line)
                if m:
                    current["num_residues"] = int(m.group(1))

        if current:
            pockets.append(current)
    except Exception as e:
        logger.warning("Failed to parse fpocket infos.txt: %s", e)

    # Parse pocket PDB files for centroid and residue list
    pockets_dir = out_dir / "pockets"
    for pocket in pockets:
        pocket_id = pocket["id"]
        pocket_pdb = pockets_dir / f"pocket{pocket_id}_atm.pdb"
        if pocket_pdb.exists():
            _enrich_pocket_from_pdb(pocket, pocket_pdb)

    # Compute radii from centroid + farthest residue
    for pocket in pockets:
        if pocket["centroid"] != [0.0, 0.0, 0.0] and pocket.get("residues"):
            # Radius approximated from volume: V = (4/3)πr³ → r = (3V/4π)^(1/3)
            vol = pocket["volume"]
            if vol > 0:
                pocket["radius"] = round((3 * vol / (4 * math.pi)) ** (1/3), 2)

    total_residues = sum(p["num_residues"] for p in pockets) if pockets else 0

    return {
        "pdb_id": pdb_id,
        "probe_radius": probe_radius,
        "total_residues": total_residues,
        "pockets": [
            {
                "id": p["id"],
                "area_sa": round(p["area_sa"], 1),
                "volume_sa": round(p["volume"], 1),
                "num_residues": p["num_residues"],
                "residues": p.get("residues", []),
                "centroid": [round(c, 2) for c in p["centroid"]],
                "radius": round(p["radius"], 2),
            }
            for p in pockets
        ],
    }


def _enrich_pocket_from_pdb(pocket: dict, pdb_path: Path) -> None:
    """Extract centroid and residue list from fpocket's pocket PDB file."""
    xs, ys, zs = [], [], []
    residues: list[str] = []
    seen_res: set[str] = set()

    try:
        for line in pdb_path.read_text().splitlines():
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                xs.append(x)
                ys.append(y)
                zs.append(z)
            except (ValueError, IndexError):
                continue

            # Extract residue identifier
            try:
                chain = line[21].strip() or "A"
                resname = line[17:20].strip()
                resseq = line[22:26].strip()
                res_key = f"{chain}{resseq}{resname}"
                if res_key not in seen_res:
                    seen_res.add(res_key)
                    residues.append(res_key)
            except IndexError:
                pass
    except Exception:
        pass

    if xs:
        pocket["centroid"] = [
            sum(xs) / len(xs),
            sum(ys) / len(ys),
            sum(zs) / len(zs),
        ]
    if residues:
        pocket["residues"] = residues
        pocket["num_residues"] = len(residues)


def _empty_result(pdb_id: str, probe_radius: float, total_residues: int) -> dict:
    return {
        "pdb_id": pdb_id,
        "probe_radius": probe_radius,
        "total_residues": total_residues,
        "pockets": [],
    }


# ---------------------------------------------------------------------------
# SASA fallback (Biopython ShrakeRupley + KDTree clustering)
# ---------------------------------------------------------------------------

def _analyze_pockets_sasa_sync(pdb_text: str, pdb_id: str, probe_radius: float) -> dict:
    """Compute per-residue SASA and detect pockets via clustering."""
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

    pockets = _detect_pockets_sasa(residues_sasa, coords, probe_radius)

    return {
        "pdb_id": pdb_id,
        "probe_radius": probe_radius,
        "total_residues": len(residues_sasa),
        "pockets": pockets,
    }


def _detect_pockets_sasa(residues: list[dict], coords: list[tuple], probe_radius: float) -> list[dict]:
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

        residues_list = [
            f"{r['chain']}{r['resnum']}{r['residue']}" for r in cluster_residues
        ]

        pockets.append({
            "id": idx + 1,
            "area_sa": round(avg_sasa * len(cluster_residues), 1),
            "volume_sa": round(volume, 1),
            "num_residues": len(cluster_residues),
            "residues": residues_list,
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


# ---------------------------------------------------------------------------
# Structure summary (chains + residue details + gap ranges)
# ---------------------------------------------------------------------------

_PDB_AA = {
    "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F", "GLY": "G",
    "HIS": "H", "ILE": "I", "LYS": "K", "LEU": "L", "MET": "M", "ASN": "N",
    "PRO": "P", "GLN": "Q", "ARG": "R", "SER": "S", "THR": "T", "VAL": "V",
    "TRP": "W", "TYR": "Y",
}


def _parse_pdb_chains(pdb_text: str) -> dict:
    """Parse PDB into per-chain ordered residue records (only those with coords).

    Returns {chains: [{id, residues: [{num, name, one}...]}], by_key: {chain: {num: name}}}
    """
    order: dict[str, list[dict]] = {}
    seen: dict[tuple, bool] = {}
    for line in pdb_text.splitlines():
        if not line.startswith("ATOM"):
            continue
        chain = line[21].strip() or "A"
        resname = line[17:20].strip()
        try:
            resseq = int(line[22:26].strip())
        except (ValueError, IndexError):
            continue
        key = (chain, resseq)
        if key in seen:
            continue
        seen[key] = True
        order.setdefault(chain, []).append({
            "num": resseq,
            "name": resname,
            "one": _PDB_AA.get(resname, resname),
        })
    chains = [
        {"id": cid, "residues": res}
        for cid, res in sorted(order.items())
    ]
    for chain in chains:
        chain["residues"].sort(key=lambda r: r["num"])
    return {"chains": chains}


def _chain_sequence(residues: list[dict]) -> str:
    return "".join(r["one"] for r in residues)


def _residue_key(chain: str, num: int) -> str:
    return f"{chain}{num}"


def _coverage_gaps(residues: list[dict]) -> list[dict]:
    """Missing-residue (coordinate) gaps within a modelled/observed chain."""
    gaps = []
    nums = [r["num"] for r in residues]
    if len(nums) < 2:
        return gaps
    prev = nums[0]
    for n in nums[1:]:
        if n > prev + 1:
            gaps.append({"start": prev + 1, "end": n - 1, "count": n - prev - 1})
        prev = n
    return gaps


def _pocket_gap_ranges(chain: dict, pocket_nums: set[int]) -> list[dict]:
    """Calculate lining-residue gaps: for each gap between pocket residues in a
    chain, report the residues present in the chain but not lining the pocket."""
    residues = chain["residues"]
    nums = [r["num"] for r in residues]
    if len(nums) < 2:
        return []
    gaps = []
    prev_pocket = None
    for n in nums:
        in_pocket = n in pocket_nums
        if in_pocket:
            if prev_pocket is not None and n > prev_pocket + 1:
                in_between = [r for r in residues if prev_pocket < r["num"] < n]
                non_lining = [r for r in in_between if r["num"] not in pocket_nums]
                if non_lining:
                    gaps.append({
                        "start": non_lining[0]["num"],
                        "end": non_lining[-1]["num"],
                        "count": len(non_lining),
                        "coordinate_present": True,
                    })
            prev_pocket = n
    return gaps


def _attach_structure_summary(pdb_text: str, result: dict) -> None:
    """Enrich a pocket-analysis result with chain info, structured pocket
    residues, and gap ranges for the structure and each pocket."""
    try:
        parsed = _parse_pdb_chains(pdb_text)
    except Exception as exc:
        logger.warning("Structure summary parse failed: %s", exc)
        return

    chains_out = []
    chains = parsed["chains"]
    for chain in chains:
        one = _chain_sequence(chain["residues"])
        chains_out.append({
            "id": chain["id"],
            "residue_count": len(chain["residues"]),
            "sequence": one,
            "gaps": _coverage_gaps(chain["residues"]),
        })
    result["chains"] = chains_out

    # Build lookup: chain -> {num: residue}
    by_num = {
        chain["id"]: {r["num"]: r for r in chain["residues"]}
        for chain in chains
    }

    for pocket in result.get("pockets", []):
        raw = pocket.get("residues", [])
        parsed_res = []
        for entry in raw:
            # entries look like "A10GLY" or "A10CYS"
            m = re.match(r"([A-Za-z0-9])(\d+)([A-Za-z]+)", entry)
            chain = ""
            num = 0
            name = entry
            if m:
                chain = m.group(1)
                num = int(m.group(2))
                name = m.group(3)
            # cross-check against coordinates
            coord_present = False
            if chain in by_num and num in by_num[chain] and by_num[chain][num]["name"] == name:
                coord_present = True
            parsed_res.append({
                "chain": chain,
                "residue_number": num,
                "residue_name": name,
                "one": _PDB_AA.get(name, name),
                "label": f"{chain}{num}{name}",
                "coordinate_present": coord_present,
            })
        pocket["residue_details"] = parsed_res

        # gap ranges per chain in the pocket
        pocket_nums_by_chain: dict[str, set[int]] = {}
        for r in parsed_res:
            if r["chain"]:
                pocket_nums_by_chain.setdefault(r["chain"], set()).add(r["residue_number"])

        pocket_gap_ranges = []
        for chain in chains:
            nums = pocket_nums_by_chain.get(chain["id"])
            if not nums:
                continue
            gaps = _pocket_gap_ranges(chain, nums)
            if gaps:
                pocket_gap_ranges.append({"chain": chain["id"], "gaps": gaps})
        pocket["gap_ranges"] = pocket_gap_ranges

        # chain span summary
        spans = {}
        for r in parsed_res:
            if not r["chain"]:
                continue
            s = spans.setdefault(r["chain"], {"min": r["residue_number"], "max": r["residue_number"], "count": 0})
            s["min"] = min(s["min"], r["residue_number"])
            s["max"] = max(s["max"], r["residue_number"])
            s["count"] += 1
        pocket["chain_spans"] = [{"chain": k, **v} for k, v in spans.items()]
