from __future__ import annotations

import asyncio
import json
import math
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional

from app.services.supabase import get_client

router = APIRouter(prefix="/api/docking", tags=["Docking"])
_TABLE = "docking_jobs"


# ---------------------------------------------------------------------------
# Request / response schemas (match frontend DockingResult type)
# ---------------------------------------------------------------------------

class DockingJobCreate(BaseModel):
    pdb_id: str = ""
    smiles: str
    pdb_url: str = ""
    grid_center: Optional[list[float]] = None
    grid_size: list[float] = Field(default_factory=lambda: [20.0, 20.0, 20.0])
    exhaustiveness: int = 8
    num_modes: int = 9


class DockingJobResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prune_old(supabase, max_rows: int = 200):
    try:
        rows = (
            supabase.table(_TABLE)
            .select("id")
            .order("created_at", desc=True)
            .range(max_rows, max_rows + 1000)
            .execute()
            .data
        )
        if rows:
            supabase.table(_TABLE).delete().in_(
                "id", [r["id"] for r in rows]
            ).execute()
    except Exception:
        pass


def _row_to_response(row: dict) -> dict:
    """Convert a Supabase row to the frontend DockingResult shape."""
    result = None
    if row.get("result_sdf"):
        try:
            result = json.loads(row["result_sdf"])
        except Exception:
            pass
    return {
        "job_id": row["id"],
        "status": row["status"],
        "result": result,
        "error": row.get("error"),
    }


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _run_docking_sync(job_id: str, payload: dict):
    """Run the full docking pipeline synchronously (in a thread)."""
    supabase = get_client()
    try:
        supabase.table(_TABLE).update({"status": "running"}).eq("id", job_id).execute()

        from app.tools.docking import (
            fetch_pdb_from_rcsb,
            compute_grid_center,
            smiles_to_pdbqt,
            pdb_to_pdbqt_receptor,
            run_vina,
        )
        import urllib.request

        pdb_id = payload.get("pdb_id", "").strip().upper()
        pdb_url = payload.get("pdb_url", "").strip()
        smiles = payload.get("ligand_smiles") or payload.get("smiles")
        if not smiles:
            raise ValueError("Missing ligand_smiles in job payload")

        # 1. Obtain PDB text
        pdb_text: str | None = None
        if pdb_url:
            try:
                pdb_text = urllib.request.urlopen(pdb_url, timeout=30).read().decode("utf-8", errors="replace")
            except Exception:
                pass
        if not pdb_text and pdb_id:
            pdb_text = fetch_pdb_from_rcsb(pdb_id)

        if not pdb_text:
            raise RuntimeError(
                "Could not obtain a PDB structure. "
                "Provide a valid pdb_id or pdb_url."
            )

        # 2. Strip heteroatoms (keep protein backbone for receptor)
        protein_lines = [
            l for l in pdb_text.splitlines()
            if l.startswith("ATOM") or l.startswith("TER") or l.startswith("END")
        ]
        protein_pdb = "\n".join(protein_lines) if protein_lines else pdb_text

        # 3. Compute grid center if not provided
        grid_center = payload.get("grid_center")
        if not grid_center or all(v == 0 for v in grid_center):
            grid_center = compute_grid_center(protein_pdb)
            # Add a small offset so the center isn't dead on a backbone atom
            grid_center = [round(c + 2.0, 3) for c in grid_center]

        grid_size = payload.get("grid_size", [20.0, 20.0, 20.0])

        # 4. Prepare receptor
        protein_pdbqt = pdb_to_pdbqt_receptor(protein_pdb)

        # 5. Prepare ligand
        lig_pdbqt = smiles_to_pdbqt(smiles)

        # 6. Run AutoDock Vina
        vina_result = run_vina(
            protein_pdbqt=protein_pdbqt,
            ligand_pdbqt=lig_pdbqt,
            grid_center=grid_center,
            grid_size=grid_size,
            exhaustiveness=payload.get("exhaustiveness", 8),
            num_modes=payload.get("num_modes", 9),
        )

        # 7. Compute interaction summary for best pose
        interactions = _compute_interactions(
            protein_pdb, vina_result["ligand_pdb"]
        )
        pose_interactions = _summarize_pose_interactions(
            protein_pdb, vina_result.get("result_sdf", "")
        )

        result_obj = {
            "pdb_id": pdb_id,
            "smiles": smiles,
            "poses": vina_result["poses"],
            "num_poses": vina_result["num_poses"],
            "box_center": {
                "x": grid_center[0],
                "y": grid_center[1],
                "z": grid_center[2],
            },
            "box_size": {
                "x": grid_size[0],
                "y": grid_size[1],
                "z": grid_size[2],
            },
            "vina_log": vina_result.get("vina_log", ""),
            "interactions": interactions,
            "pose_interactions": pose_interactions,
            "ligand_pdb": vina_result.get("ligand_pdb", ""),
        }

        supabase.table(_TABLE).update({
            "status": "completed",
            "result_sdf": json.dumps(result_obj),
        }).eq("id", job_id).execute()

    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        supabase.table(_TABLE).update({
            "status": "failed",
            "error": f"{exc}\n\n{tb}"[:4000],
        }).eq("id", job_id).execute()
    finally:
        _prune_old(supabase)


# ---------------------------------------------------------------------------
# Geometric interaction detector (H-bonds, hydrophobic, pi-stacking, salt bridges)
# ---------------------------------------------------------------------------

    # Protein atom classification
_HYDROPHOBIC_RES = {"ALA", "VAL", "LEU", "ILE", "MET", "PHE", "TRP", "PRO", "GLY"}
_AROMATIC_RES = {"PHE", "TRP", "TYR", "HIS"}

# Atoms in aromatic rings by residue (PDB atom names)
_AROMATIC_RING_ATOMS = {
    "PHE": ["CG", "CD1", "CD2", "CE1", "CE2", "CZ"],
    "TYR": ["CG", "CD1", "CD2", "CE1", "CE2", "CZ"],
    "HIS": ["CG", "ND1", "CD2", "CE1", "NE2"],
    "TRP": ["CG", "CD1", "CD2", "NE1", "CE2", "CE3", "CZ2", "CZ3", "CH2"],
}

# Two-ring centroids for TRP (5-membered + 6-membered)
_TRP_RINGS = {
    "five": ["CD1", "NE1", "CE2", "CG", "CD2"],
    "six": ["CE2", "CD2", "CZ2", "CH2", "CZ3", "CE3"],
}

# Polar atoms eligible for H-bonding
_POLAR_ATOMS = {"N", "O", "S"}

# Residue-level charge groups for salt bridges
_ANIONIC_RES = {"ASP", "GLU"}
_CATIONIC_RES = {"LYS", "ARG", "HIS"}

# Atom names that define the charged group center
_ANIONIC_CARBONS = {"ASP": "CG", "GLU": "CD"}
_CATIONIC_NITROGENS = {"LYS": "NZ", "ARG": ["CZ", "NH1", "NH2"]}

_PDB_COORD_RE = re.compile(
    r"^(ATOM|HETATM)\s+\d+\s+(\S+)\s+(\S{3})\s+(\S)\s+(\d+)\s+"
    r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"
)


def _parse_atom_coords(pdb_text: str) -> list[tuple[str, str, str, str, int, float, float, float]]:
    """Parse PDB into (record, atom_name, res_name, chain, res_seq, x, y, z)."""
    atoms = []
    for line in pdb_text.splitlines():
        m = _PDB_COORD_RE.match(line)
        if m:
            atoms.append((
                m.group(1), m.group(2), m.group(3), m.group(4),
                int(m.group(5)),
                float(m.group(6)), float(m.group(7)), float(m.group(8)),
            ))
    return atoms


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _angle(a: tuple[float, float, float], b: tuple[float, float, float],
           c: tuple[float, float, float]) -> float:
    """Angle at vertex b between segments b→a and b→c, in degrees."""
    ba = tuple(x - y for x, y in zip(a, b))
    bc = tuple(x - y for x, y in zip(c, b))
    dot = sum(x * y for x, y in zip(ba, bc))
    mag_ba = math.sqrt(sum(x * x for x in ba))
    mag_bc = math.sqrt(sum(x * x for x in bc))
    if mag_ba < 1e-9 or mag_bc < 1e-9:
        return 0.0
    cos_angle = max(-1.0, min(1.0, dot / (mag_ba * mag_bc)))
    return math.degrees(math.acos(cos_angle))


def _vec_sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vec_cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _vec_norm(v: tuple[float, float, float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _ring_centroid(coords: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    n = len(coords)
    if n == 0:
        return (0.0, 0.0, 0.0)
    return (
        sum(c[0] for c in coords) / n,
        sum(c[1] for c in coords) / n,
        sum(c[2] for c in coords) / n,
    )


def _ring_normal(coords: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    """Compute the normal vector of a planar ring via cross product of two edges."""
    if len(coords) < 3:
        return (0.0, 0.0, 1.0)
    v1 = _vec_sub(coords[1], coords[0])
    v2 = _vec_sub(coords[2], coords[0])
    cross = _vec_cross(v1, v2)
    n = _vec_norm(cross)
    if n < 1e-9:
        return (0.0, 0.0, 1.0)
    return (cross[0] / n, cross[1] / n, cross[2] / n)


def _build_residue_map(atoms: list[tuple]) -> dict[tuple[str, str, int], list[tuple]]:
    """Group atoms by (chain, res_name, res_seq)."""
    res_map: dict[tuple[str, str, int], list[tuple]] = {}
    for a in atoms:
        key = (a[3], a[2], a[4])  # chain, res_name, res_seq
        res_map.setdefault(key, []).append(a)
    return res_map


def _find_hydrogens(atoms: list[tuple]) -> list[tuple]:
    """Return only hydrogen atoms from parsed PDB."""
    return [a for a in atoms if a[1].startswith("H") or a[1] in ("1H", "2H", "3H")]


def _compute_interactions(protein_pdb: str, ligand_pdb: str) -> dict:
    """
    Compute protein-ligand interactions using proper geometry.

    H-bonds:     donor-H···acceptor angle > 120°, distance < 3.5Å
    Hydrophobic: ligand carbon near protein carbon in hydrophobic residue, < 4.5Å
    Pi-stacking: aromatic ring centroids, distance < 5.5Å, inter-ring angle
    Salt bridges: charged group centroids, distance < 4.0Å
    """
    if not ligand_pdb:
        return {"hbonds": [], "hydrophobic": [], "pi_stacking": [], "salt_bridges": []}

    prot_atoms = _parse_atom_coords(protein_pdb)
    lig_atoms = _parse_atom_coords(ligand_pdb)
    prot_h = _find_hydrogens(prot_atoms)
    lig_h = _find_hydrogens(lig_atoms)
    prot_heavy = [a for a in prot_atoms if not (a[1].startswith("H") or a[1] in ("1H", "2H", "3H"))]
    lig_heavy = [a for a in lig_atoms if not (a[1].startswith("H") or a[1] in ("1H", "2H", "3H"))]

    hbonds: list[dict] = []
    hydrophobic: list[dict] = []
    pi_stacking: list[dict] = []
    salt_bridges: list[dict] = []

    seen_hbonds: set[tuple] = set()
    seen_hydrophobic: set[tuple] = set()
    seen_salt: set[tuple] = set()

    # --- H-bonds with angle check ---
    for la in lig_heavy:
        l_elem = la[1][0] if la[1] else ""
        if l_elem not in _POLAR_ATOMS:
            continue
        lcoord = (la[5], la[6], la[7])

        # Find nearest H on ligand for angle reference
        lig_h_near = None
        min_h_dist = 1.5
        for h in lig_h:
            hd = _distance(lcoord, (h[5], h[6], h[7]))
            if hd < min_h_dist:
                min_h_dist = hd
                lig_h_near = (h[5], h[6], h[7])

        for pa in prot_heavy:
            p_elem = pa[1][0] if pa[1] else ""
            if p_elem not in _POLAR_ATOMS:
                continue
            pcoord = (pa[5], pa[6], pa[7])
            d = _distance(lcoord, pcoord)

            if d > 3.5 or d < 1.0:
                continue

            # Find nearest H on protein donor for angle check
            prot_h_near = None
            min_ph_dist = 1.5
            for h in prot_h:
                hd = _distance(pcoord, (h[5], h[6], h[7]))
                if hd < min_ph_dist:
                    min_ph_dist = hd
                    prot_h_near = (h[5], h[6], h[7])

            # Check angle if we have hydrogen positions
            angle_ok = True
            if lig_h_near and prot_h_near:
                # H-bond angle: ligand-H···protein or protein-H···ligand
                a1 = _angle(lig_h_near, lcoord, pcoord)
                a2 = _angle(prot_h_near, pcoord, lcoord)
                angle_ok = max(a1, a2) > 120.0
            elif lig_h_near:
                a1 = _angle(lig_h_near, lcoord, pcoord)
                angle_ok = a1 > 120.0
            elif prot_h_near:
                a1 = _angle(prot_h_near, pcoord, lcoord)
                angle_ok = a1 > 120.0
            # If no H found at all, accept based on distance + element only

            if not angle_ok:
                continue

            key = (la[4], pa[4])  # (lig_res_seq, prot_res_seq)
            if key in seen_hbonds:
                continue
            seen_hbonds.add(key)

            hbonds.append({
                "type": "hbond",
                "ligand_atom": la[1],
                "ligand_coords": [la[5], la[6], la[7]],
                "protein_residue": pa[2],
                "protein_residue_seq": pa[4],
                "protein_chain": pa[3],
                "protein_atom": pa[1],
                "protein_coords": [pa[5], pa[6], pa[7]],
                "distance": round(d, 2),
                "confidence": "high" if d < 3.0 else "medium",
            })
            if len(hbonds) >= 20:
                break
        if len(hbonds) >= 20:
            break

    # --- Hydrophobic contacts ---
    for la in lig_heavy:
        if la[1][0] != "C":
            continue
        lcoord = (la[5], la[6], la[7])
        for pa in prot_heavy:
            if pa[1][0] != "C":
                continue
            pres = pa[2]
            if pres not in _HYDROPHOBIC_RES:
                continue
            pcoord = (pa[5], pa[6], pa[7])
            d = _distance(lcoord, pcoord)
            if d < 4.5:
                key = (la[4], pa[4])
                if key in seen_hydrophobic:
                    continue
                seen_hydrophobic.add(key)
                hydrophobic.append({
                    "type": "hydrophobic",
                    "ligand_atom": la[1],
                    "ligand_coords": [la[5], la[6], la[7]],
                    "protein_residue": pres,
                    "protein_residue_seq": pa[4],
                    "protein_chain": pa[3],
                    "protein_atom": pa[1],
                    "protein_coords": [pa[5], pa[6], pa[7]],
                    "distance": round(d, 2),
                })
                if len(hydrophobic) >= 20:
                    break
        if len(hydrophobic) >= 20:
            break

    # --- Pi-stacking (aromatic ring centroid geometry) ---
    prot_res_map = _build_residue_map(prot_heavy)

    for res_key, res_atoms in prot_res_map.items():
        chain, res_name, res_seq = res_key
        if res_name not in _AROMATIC_RES:
            continue

        ring_atom_names = _AROMATIC_RING_ATOMS[res_name]
        ring_atoms_by_name = {a[1]: a for a in res_atoms}
        ring_coords = []
        for rn in ring_atom_names:
            if rn in ring_atoms_by_name:
                a = ring_atoms_by_name[rn]
                ring_coords.append((a[5], a[6], a[7]))

        if len(ring_coords) < 3:
            continue

        centroid = _ring_centroid(ring_coords)
        normal = _ring_normal(ring_coords)

        # For TRP, also check the 5-membered ring
        rings_to_check = [(ring_coords, centroid, normal)]
        if res_name == "TRP":
            for ring_name in ("five", "six"):
                ring_atom_names_2 = _TRP_RING_ATOMS[ring_name]
                coords_2 = []
                for rn in ring_atom_names_2:
                    if rn in ring_atoms_by_name:
                        a = ring_atoms_by_name[rn]
                        coords_2.append((a[5], a[6], a[7]))
                if len(coords_2) >= 3:
                    rings_to_check.append((coords_2, _ring_centroid(coords_2), _ring_normal(coords_2)))

        for ring_coords_r, centroid_r, normal_r in rings_to_check:
            # Find aromatic atoms in ligand (heuristic: C/N in a flat region)
            lig_aromatic_coords = []
            for la in lig_heavy:
                if la[1][0] in ("C", "N"):
                    lig_aromatic_coords.append((la[5], la[6], la[7]))

            if len(lig_aromatic_coords) < 3:
                continue

            # Use all ligand heavy atoms as a pseudo-centroid
            lig_centroid = _ring_centroid(lig_aromatic_coords)

            dist = _distance(centroid_r, lig_centroid)
            if dist > 6.5:
                continue

            # Compute angle between ring normal and vector to ligand centroid
            v_to_lig = _vec_sub(lig_centroid, centroid_r)
            v_norm = _vec_norm(v_to_lig)
            if v_norm < 1e-9:
                continue
            cos_angle = abs(sum(x * y for x, y in zip(normal_r, v_to_lig))) / (
                _vec_norm(normal_r) * v_norm
            )
            ring_angle = math.degrees(math.acos(max(0, min(1, cos_angle))))

            # Parallel: ring normal ~parallel to centroid-centroid vector (angle < 30°)
            # T-shaped: ring normal ~perpendicular (angle 60-90°)
            stacking_type = "unknown"
            if ring_angle < 30 and dist < 5.5:
                stacking_type = "parallel"
            elif 60 < ring_angle < 90 and dist < 6.5:
                stacking_type = "perpendicular"

            if stacking_type == "unknown":
                continue

            pi_stacking.append({
                "type": "pi_stacking",
                "protein_residue": res_name,
                "protein_residue_seq": res_seq,
                "protein_chain": chain,
                "ring_centroid": [round(c, 3) for c in centroid_r],
                "ring_normal": [round(c, 3) for c in normal_r],
                "ligand_centroid": [round(c, 3) for c in lig_centroid],
                "distance": round(dist, 2),
                "angle": round(ring_angle, 1),
                "stacking_type": stacking_type,
                "confidence": "high" if dist < 4.5 else "medium",
            })
            if len(pi_stacking) >= 10:
                break
        if len(pi_stacking) >= 10:
            break

    # --- Salt bridges (charged group centroid distance) ---
    for la in lig_heavy:
        l_elem = la[1][0] if la[1] else ""
        if l_elem not in ("N", "O", "S", "C"):
            continue
        lcoord = (la[5], la[6], la[7])

        for pa in prot_heavy:
            pres = pa[2]
            if pres in _ANIONIC_RES and pa[1] in ("OD1", "OD2", "OE1", "OE2"):
                d = _distance(lcoord, pa[1:8] if False else (pa[5], pa[6], pa[7]))
                if d < 4.0 and l_elem in ("N",):
                    key = (la[4], pa[4])
                    if key not in seen_salt:
                        seen_salt.add(key)
                        salt_bridges.append({
                            "type": "salt_bridge",
                            "ligand_atom": la[1],
                            "ligand_coords": [la[5], la[6], la[7]],
                            "protein_residue": pres,
                            "protein_residue_seq": pa[4],
                            "protein_chain": pa[3],
                            "protein_atom": pa[1],
                            "protein_coords": [pa[5], pa[6], pa[7]],
                            "distance": round(d, 2),
                            "charge_pair": "positive-negative",
                        })

            if pres in _CATIONIC_RES:
                cat_atoms = _CATIONIC_NITROGENS.get(pres, [])
                if isinstance(cat_atoms, str):
                    cat_atoms = [cat_atoms]
                if pa[1] in cat_atoms:
                    d = _distance(lcoord, (pa[5], pa[6], pa[7]))
                    if d < 4.0 and l_elem in ("O",):
                        key = (la[4], pa[4])
                        if key not in seen_salt:
                            seen_salt.add(key)
                            salt_bridges.append({
                                "type": "salt_bridge",
                                "ligand_atom": la[1],
                                "ligand_coords": [la[5], la[6], la[7]],
                                "protein_residue": pres,
                                "protein_residue_seq": pa[4],
                                "protein_chain": pa[3],
                                "protein_atom": pa[1],
                                "protein_coords": [pa[5], pa[6], pa[7]],
                                "distance": round(d, 2),
                                "charge_pair": "negative-positive",
                            })

    return {
        "hbonds": hbonds[:20],
        "hydrophobic": hydrophobic[:20],
        "pi_stacking": pi_stacking[:10],
        "salt_bridges": salt_bridges[:10],
    }


def _summarize_pose_interactions(protein_pdb: str, output_pdbqt: str) -> list[dict]:
    """Per-pose interaction summary."""
    if not output_pdbqt:
        return []
    models: dict[int, list[str]] = {}
    current: int | None = None
    for line in output_pdbqt.splitlines():
        if line.startswith("MODEL"):
            parts = line.split()
            if len(parts) >= 2:
                current = int(parts[1])
                models[current] = []
        elif line.startswith("ENDMDL"):
            current = None
        elif current is not None:
            models.setdefault(current, []).append(line)

    summaries = []
    for mid in sorted(models.keys()):
        lig_pdb = "\n".join(l for l in models[mid] if l.startswith("HETATM")) + "\nEND"
        inter = _compute_interactions(protein_pdb, lig_pdb)
        summaries.append({
            "model": mid,
            "hbonds": len(inter.get("hbonds", [])),
            "hydrophobic": len(inter.get("hydrophobic", [])),
            "pi_stacking": len(inter.get("pi_stacking", [])),
            "salt_bridges": len(inter.get("salt_bridges", [])),
        })
    return summaries


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@router.post("/run", response_model=DockingJobResponse)
async def create_docking_job(body: DockingJobCreate):
    supabase = get_client()
    _prune_old(supabase)

    import uuid, datetime
    job_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()

    # Only INSERT columns guaranteed to exist in every Supabase docking_jobs schema.
    # Runtime params (grid, exhaustiveness, etc.) are passed to the worker in-memory.
    insert_row = {
        "id": job_id,
        "status": "queued",
        "ligand_smiles": body.smiles,
    }
    try:
        supabase.table(_TABLE).insert(insert_row).execute()
    except Exception as e:
        # If even ligand_smiles is missing, try bare minimum
        if "ligand_smiles" in str(e):
            supabase.table(_TABLE).insert({"id": job_id, "status": "queued"}).execute()
        else:
            raise

    # Pass full params to the background worker (not stored in DB)
    worker_payload = {
        **insert_row,
        "pdb_id": body.pdb_id,
        "pdb_url": body.pdb_url,
        "grid_center": body.grid_center or [0, 0, 0],
        "grid_size": body.grid_size,
        "exhaustiveness": body.exhaustiveness,
        "num_modes": body.num_modes,
    }
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(loop.run_in_executor(None, _run_docking_sync, job_id, worker_payload))

    return DockingJobResponse(job_id=job_id, status="queued", result=None)


@router.get("/status/{job_id}", response_model=DockingJobResponse)
async def get_docking_job(job_id: str):
    supabase = get_client()
    result = supabase.table(_TABLE).select("*").eq("id", job_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Docking job not found")
    return DockingJobResponse(**_row_to_response(result.data))


@router.get("/result/{job_id}/pdb")
async def get_docking_pdb(job_id: str):
    supabase = get_client()
    result = supabase.table(_TABLE).select("result_sdf").eq("id", job_id).single().execute()
    if not result.data or not result.data.get("result_sdf"):
        raise HTTPException(status_code=404, detail="Docking result not found")
    try:
        data = json.loads(result.data["result_sdf"])
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid result data")
    ligand_pdb = data.get("ligand_pdb", "")
    if not ligand_pdb:
        raise HTTPException(status_code=404, detail="No ligand PDB available")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(ligand_pdb, media_type="text/plain")


@router.get("")
async def list_docking_jobs(limit: int = 50):
    supabase = get_client()
    rows = (
        supabase.table(_TABLE)
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    return {"jobs": [_row_to_response(r) for r in rows]}
