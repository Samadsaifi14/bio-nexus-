import asyncio
import logging
import math
import os
import re
import shutil
import sys
import tempfile
import time
from typing import Any

import httpx

from app.tools.base import BaseTool

logger = logging.getLogger(__name__)

PDB_DOWNLOAD = "https://files.rcsb.org/download/{pdb_id}.pdb"
def _find_obabel() -> str | None:
    """Locate the obabel CLI — check PATH first, then Python's bin dir (openbabel-wheel installs there), then common system paths."""
    cmd = shutil.which("obabel")
    if cmd:
        return cmd
    extra = os.pathsep.join([
        os.path.dirname(sys.executable) if sys.executable else "",
        "/usr/local/bin",
        "/usr/bin",
    ])
    return shutil.which("obabel", path=extra)

VINA_CMD = shutil.which("vina") or "/usr/local/bin/vina"
OBABEL_CMD = _find_obabel()

# ── in-process OpenBabel bindings (no subprocess – saves ~200 MB RAM) ───

def _pdb_to_pdbqt_pybel(pdb_path: str, out_path: str) -> bool:
    try:
        from openbabel import pybel
        mol = next(pybel.readfile("pdb", pdb_path))
        mol.write("pdbqt", out_path, overwrite=True)
        return os.path.exists(out_path)
    except Exception:
        return False


def _smiles_to_pdbqt_pybel(smiles: str, out_path: str) -> bool:
    try:
        from openbabel import pybel
        mol = pybel.readstring("smi", smiles)
        mol.addh()
        mol.make3D()
        mol.write("pdbqt", out_path, overwrite=True)
        return os.path.exists(out_path)
    except Exception:
        return False

# ── self-healing binary download ─────────────────────────────────────────
_VINA_URL = "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.7/vina_1.2.7_linux_x86_64"

def _pip_install_obabel() -> str | None:
    """Install openbabel-wheel via pip and return the obabel path."""
    import subprocess as _sp
    logger.info("obabel not found — installing openbabel-wheel via pip")
    try:
        _sp.run([sys.executable, "-m", "pip", "install", "openbabel-wheel", "-q"],
                capture_output=True, timeout=120)
    except Exception as exc:
        logger.warning("pip install openbabel-wheel failed: %s", exc)
        return None
    return _find_obabel()

def _download_vina(dest: str) -> str | None:
    """Download the Vina binary to *dest*."""
    import urllib.request as _ur
    try:
        logger.info("Downloading AutoDock Vina binary …")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        _ur.urlretrieve(_VINA_URL, dest)
        os.chmod(dest, 0o755)
    except Exception as exc:
        logger.warning("Failed to download Vina: %s", exc)
        return None
    return dest if os.path.isfile(dest) else None

# ── interaction cutoffs ──────────────────────────────────────────────────
HBOND_DIST = 3.5      # donor–acceptor heavy-atom distance (Å)
HYDROPHOBIC_DIST = 4.0
PI_STACK_CENTROID_DIST = 4.5
PI_STACK_ANGLE_TOL = 30  # degrees from parallel/perpendicular

AROMATIC_RESIDUES = {"PHE", "TYR", "TRP", "HIS"}
AROMATIC_ATOMS = {"CG", "CD1", "CD2", "CE1", "CE2", "CZ", "CZ2", "CZ3", "CH2", "ND1", "NE1", "CD", "NE2"}
# ring centroids used: PHE, TYR, TRP(five+six), HIS


# ── helpers ──────────────────────────────────────────────────────────────
def _find_ligand_center(pdb_content: str) -> tuple[float, float, float] | None:
    het_atoms: list[list[tuple[float, float, float]]] = []
    current_het: list[tuple[float, float, float]] = []
    current_resname = ""
    for line in pdb_content.splitlines():
        if line.startswith("HETATM"):
            resname = line[17:20].strip()
            if resname == "HOH":
                continue
            try:
                x = float(line[30:38].strip())
                y = float(line[38:46].strip())
                z = float(line[46:54].strip())
            except ValueError:
                continue
            if resname != current_resname:
                if current_het:
                    het_atoms.append(current_het)
                current_het = [(x, y, z)]
                current_resname = resname
            else:
                current_het.append((x, y, z))
        elif line.startswith("ATOM") or line.startswith("TER"):
            if current_het:
                het_atoms.append(current_het)
                current_het = []
                current_resname = ""
    if current_het:
        het_atoms.append(current_het)

    if not het_atoms:
        return None

    largest = max(het_atoms, key=len)
    cx = sum(a[0] for a in largest) / len(largest)
    cy = sum(a[1] for a in largest) / len(largest)
    cz = sum(a[2] for a in largest) / len(largest)
    return cx, cy, cz


def _find_protein_center(pdb_content: str) -> tuple[float, float, float]:
    xs, ys, zs = [], [], []
    for line in pdb_content.splitlines():
        if line.startswith("ATOM") and len(line) >= 54:
            try:
                xs.append(float(line[30:38].strip()))
                ys.append(float(line[38:46].strip()))
                zs.append(float(line[46:54].strip()))
            except ValueError:
                continue
    if not xs:
        return 0.0, 0.0, 0.0
    return sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs)


def _clean_protein(pdb_content: str) -> str:
    lines: list[str] = []
    for line in pdb_content.splitlines():
        if line.startswith("ATOM") and len(line) >= 54:
            lines.append(line)
        elif line.startswith("TER"):
            lines.append(line)
        elif line.startswith("END"):
            lines.append(line)
    return "\n".join(lines)


# ── parsing Vina output ─────────────────────────────────────────────────
def _parse_vina_pdbqt(pdbqt: str) -> list[dict[str, Any]]:
    models = re.split(r"^MODEL\s+(\d+)", pdbqt, flags=re.MULTILINE)
    poses: list[dict[str, Any]] = []
    current_atoms: list[dict[str, Any]] = []
    current_model = 0

    for chunk in models:
        chunk = chunk.strip()
        if chunk.isdigit():
            current_model = int(chunk)
            current_atoms = []
        elif chunk and current_model > 0:
            for line in chunk.splitlines():
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    try:
                        x = float(line[30:38].strip())
                        y = float(line[38:46].strip())
                        z = float(line[46:54].strip())
                        elem = line[76:78].strip()
                        atype = line[13:16].strip() if line[13:16].strip() else elem
                        current_atoms.append({
                            "x": x, "y": y, "z": z,
                            "element": elem,
                            "atom_type": atype,
                        })
                    except ValueError:
                        continue
            if current_atoms:
                energy_match = re.search(r"REMARK VINA RESULT:\s*([-\d.]+)", chunk)
                poses.append({
                    "model": current_model,
                    "atoms": len(current_atoms),
                    "coords": current_atoms,
                    "affinity": float(energy_match.group(1)) if energy_match else None,
                })
                current_atoms = []
    return poses


# ── generating ligand PDB from coords ───────────────────────────────────
def _generate_ligand_pdb(
    coords: list[dict[str, Any]],
    resname: str = "LIG",
    chain: str = "L",
    resseq: int = 1,
) -> str:
    lines: list[str] = []
    for i, atom in enumerate(coords, start=1):
        elem = atom.get("element", "") or atom.get("atom_type", "") or ""
        elem = elem[:2].upper()
        x = atom["x"]
        y = atom["y"]
        z = atom["z"]
        lines.append(
            f"HETATM{i:>5}  {elem:<2}  {resname:<3} {chain}{resseq:>4}    "
            f"{x:>8.3f}{y:>8.3f}{z:>8.3f}  1.00  0.00           {elem:>2}"
        )
    lines.append("END")
    return "\n".join(lines)


# ── interaction fingerprinting ──────────────────────────────────────────
def _parse_protein_atoms(cleaned_pdb: str) -> list[dict[str, Any]]:
    atoms: list[dict[str, Any]] = []
    for line in cleaned_pdb.splitlines():
        if not line.startswith("ATOM"):
            continue
        try:
            x = float(line[30:38].strip())
            y = float(line[38:46].strip())
            z = float(line[46:54].strip())
        except ValueError:
            continue
        atoms.append({
            "x": x, "y": y, "z": z,
            "element": line[76:78].strip(),
            "resname": line[17:20].strip(),
            "residue_no": line[22:26].strip(),
            "chain": line[21].strip(),
            "atom_name": line[12:16].strip(),
        })
    return atoms


def _dist(a: dict, b: dict) -> float:
    dx = a["x"] - b["x"]
    dy = a["y"] - b["y"]
    dz = a["z"] - b["z"]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _is_donor(elem: str) -> bool:
    return elem in ("N", "O")


def _is_acceptor(elem: str) -> bool:
    return elem in ("N", "O", "F")


def _is_hydrophobic(elem: str) -> bool:
    return elem == "C"


def _is_side_chain(atom_name: str) -> bool:
    return atom_name not in ("N", "CA", "C", "O", "OXT", "H", "HA")


def _find_aromatic_ring_atoms(
    atoms: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """Group atoms belonging to aromatic rings (PHE, TYR, TRP, HIS)."""
    rings: list[list[dict[str, Any]]] = []
    for resname, chain, resno in {(a["resname"], a["chain"], a["residue_no"]) for a in atoms}:
        if resname not in AROMATIC_RESIDUES:
            continue
        ring_atoms = [
            a for a in atoms
            if a["resname"] == resname
            and a["chain"] == chain
            and a["residue_no"] == resno
            and a["atom_name"] in AROMATIC_ATOMS
        ]
        if not ring_atoms:
            continue

        if resname == "TRP":
            # TRP has two rings (five-membered and six-membered)
            five = [a for a in ring_atoms if a["atom_name"] in ("CG", "CD1", "CD2", "CE2", "NE1") or a["atom_name"] == "CD"]
            six = [a for a in ring_atoms if a["atom_name"] in ("CZ2", "CZ3", "CE3", "CH2")]
            # Actually TRP: 5-ring = ND1, CE2, CD2, CG, CD1; 6-ring = CZ2, CE2, CZ3, CE3, CH2, CD2
            # Let me just split by whether they fall in the six-membered set
            five_ring_atoms = [
                a for a in ring_atoms
                if a["atom_name"] in ("CG", "CD1", "CD2", "NE1", "CE2", "CD")
            ]
            six_ring_atoms = [
                a for a in ring_atoms
                if a["atom_name"] in ("CZ2", "CZ3", "CE3", "CH2", "CD2", "CE2")
            ]
            if len(five_ring_atoms) >= 4:
                rings.append(five_ring_atoms)
            if len(six_ring_atoms) >= 4:
                rings.append(six_ring_atoms)
        elif resname == "HIS":
            # HIS single ring
            if len(ring_atoms) >= 4:
                rings.append(ring_atoms)
        else:
            # PHE / TYR single six-ring
            # CG, CD1, CD2, CE1, CE2, CZ
            six_atoms = [
                a for a in ring_atoms
                if a["atom_name"] in ("CG", "CD1", "CD2", "CE1", "CE2", "CZ")
            ]
            if len(six_atoms) >= 4:
                rings.append(six_atoms)
    return rings


def _centroid(atoms: list[dict[str, Any]]) -> tuple[float, float, float]:
    cx = sum(a["x"] for a in atoms) / len(atoms)
    cy = sum(a["y"] for a in atoms) / len(atoms)
    cz = sum(a["z"] for a in atoms) / len(atoms)
    return cx, cy, cz


def _plane_normal(atoms: list[dict[str, Any]]) -> tuple[float, float, float]:
    """Least-squares plane normal via SVD of centroid-offset vectors."""
    cx, cy, cz = _centroid(atoms)
    # 3×3 covariance
    xx = xy = xz = yy = yz = zz = 0.0
    for a in atoms:
        dx = a["x"] - cx
        dy = a["y"] - cy
        dz = a["z"] - cz
        xx += dx * dx
        xy += dx * dy
        xz += dx * dz
        yy += dy * dy
        yz += dy * dz
        zz += dz * dz
    # eigenvector of smallest eigenvalue via cross-product trick
    cov = [[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]]
    # power iteration
    v = [1.0, 0.0, 0.0]
    for _ in range(20):
        v_new = [
            v[0] * cov[0][0] + v[1] * cov[0][1] + v[2] * cov[0][2],
            v[0] * cov[1][0] + v[1] * cov[1][1] + v[2] * cov[1][2],
            v[0] * cov[2][0] + v[1] * cov[2][1] + v[2] * cov[2][2],
        ]
        norm = math.sqrt(v_new[0]**2 + v_new[1]**2 + v_new[2]**2)
        if norm < 1e-12:
            break
        v = [x / norm for x in v_new]
    # v is the vector of largest eigenvalue → plane normal is orthogonal
    # We want the smallest eigenvector. Use cross product of two in-plane vectors.
    # Use Gram-Schmidt to find two orthogonal vectors in the plane.
    # Pick two atoms far apart for the first in-plane vector.
    if len(atoms) >= 3:
        a0, a1 = atoms[0], atoms[len(atoms)//2]
        dx = a1["x"] - a0["x"]
        dy = a1["y"] - a0["y"]
        dz = a1["z"] - a0["z"]
        # Project out component along v
        dot = dx * v[0] + dy * v[1] + dz * v[2]
        u1 = [dx - dot * v[0], dy - dot * v[1], dz - dot * v[2]]
        norm = math.sqrt(u1[0]**2 + u1[1]**2 + u1[2]**2)
        if norm > 1e-10:
            u1 = [x / norm for x in u1]
            # second in-plane vector = cross(v, u1)
            u2 = [
                v[1] * u1[2] - v[2] * u1[1],
                v[2] * u1[0] - v[0] * u1[2],
                v[0] * u1[1] - v[1] * u1[0],
            ]
            # normal = cross(u1, u2)
            n = [
                u1[1] * u2[2] - u1[2] * u2[1],
                u1[2] * u2[0] - u1[0] * u2[2],
                u1[0] * u2[1] - u1[1] * u2[0],
            ]
            norm = math.sqrt(n[0]**2 + n[1]**2 + n[2]**2)
            if norm > 1e-10:
                return (n[0]/norm, n[1]/norm, n[2]/norm)
    return (0.0, 0.0, 1.0)


def _angle_between(v1: tuple[float, ...], v2: tuple[float, ...]) -> float:
    dot = v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2]
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(math.acos(dot))


def _analyze_interactions(
    ligand_coords: list[dict[str, Any]],
    cleaned_protein_pdb: str,
) -> dict[str, list[dict[str, Any]]]:
    protein_atoms = _parse_protein_atoms(cleaned_protein_pdb)
    if not protein_atoms:
        return {"hbonds": [], "hydrophobic": [], "pi_stacking": []}

    # Precompute protein atom KD-tree-like search via simple loops
    hbonds: list[dict[str, Any]] = []
    hydrophobic: list[dict[str, Any]] = []
    pi_stacking: list[dict[str, Any]] = []

    # ── H-bonds and hydrophobic contacts ──
    for lig_atom in ligand_coords:
        lig_elem = lig_atom["element"]
        lig_is_donor = _is_donor(lig_elem)
        lig_is_acceptor = _is_acceptor(lig_elem)
        lig_is_hydrophobic = _is_hydrophobic(lig_elem)

        for prot_atom in protein_atoms:
            d = _dist(lig_atom, prot_atom)
            prot_elem = prot_atom["element"]
            prot_name = prot_atom["atom_name"]

            # H-bonds
            if d <= HBOND_DIST:
                if lig_is_donor and _is_acceptor(prot_elem):
                    hbonds.append({
                        "type": "hbond",
                        "ligand_atom": lig_elem,
                        "protein_atom": prot_elem,
                        "protein_residue": f'{prot_atom["resname"]}{prot_atom["residue_no"]}{prot_atom["chain"]}',
                        "protein_atom_name": prot_name,
                        "distance": round(d, 2),
                        "confidence": "potential",
                    })
                elif lig_is_acceptor and _is_donor(prot_elem):
                    hbonds.append({
                        "type": "hbond",
                        "ligand_atom": lig_elem,
                        "protein_atom": prot_elem,
                        "protein_residue": f'{prot_atom["resname"]}{prot_atom["residue_no"]}{prot_atom["chain"]}',
                        "protein_atom_name": prot_name,
                        "distance": round(d, 2),
                        "confidence": "potential",
                    })

            # Hydrophobic
            if d <= HYDROPHOBIC_DIST and lig_is_hydrophobic and _is_hydrophobic(prot_elem):
                if _is_side_chain(prot_name):
                    hydrophobic.append({
                        "type": "hydrophobic",
                        "ligand_atom": lig_elem,
                        "protein_atom": prot_elem,
                        "protein_residue": f'{prot_atom["resname"]}{prot_atom["residue_no"]}{prot_atom["chain"]}',
                        "protein_atom_name": prot_name,
                        "distance": round(d, 2),
                    })

    # Deduplicate H-bonds (keep shortest distance per residue pair)
    hbonds_dedup: dict[str, dict] = {}
    for hb in hbonds:
        key = (hb["protein_residue"], hb["ligand_atom"])
        if key not in hbonds_dedup or hb["distance"] < hbonds_dedup[key]["distance"]:
            hbonds_dedup[key] = hb
    unique_hbonds = sorted(hbonds_dedup.values(), key=lambda x: x["distance"])

    # Deduplicate hydrophobic (keep shortest)
    hydro_dedup: dict[str, dict] = {}
    for hc in hydrophobic:
        key = (hc["protein_residue"], hc["ligand_atom"])
        if key not in hydro_dedup or hc["distance"] < hydro_dedup[key]["distance"]:
            hydro_dedup[key] = hc
    unique_hydro = sorted(hydro_dedup.values(), key=lambda x: x["distance"])

    # ── Pi-stacking ──
    # Detect aromatic rings in ligand
    lig_elements = {a["element"] for a in ligand_coords}
    if "C" in lig_elements:
        # Heuristic: look for planar ring-like patterns in the ligand
        # For now, skip full ligand ring detection and check distances
        # between protein aromatic centroids and ligand carbons
        pass

    # Find protein aromatic rings
    protein_rings = _find_aromatic_ring_atoms(protein_atoms)
    if protein_rings:
        # Find ligand atoms that might be aromatic (C atoms in planar arrangement)
        # Simplified: check any large cluster of C's
        for ring in protein_rings:
            p_centroid = _centroid(ring)
            p_normal = _plane_normal(ring)
            # Check distance to other aromatic candidate centroids in ligand
            # Use nearby C atoms as a proxy
            lig_carbons = [a for a in ligand_coords if a["element"] == "C"]
            if len(lig_carbons) >= 4:
                # Try to group carbons into ring-sized clusters
                # For simplicity, check centroid of all carbons
                lig_centroid = _centroid(lig_carbons)
                cd = math.sqrt(
                    (p_centroid[0] - lig_centroid[0])**2 +
                    (p_centroid[1] - lig_centroid[1])**2 +
                    (p_centroid[2] - lig_centroid[2])**2
                )
                if cd <= PI_STACK_CENTROID_DIST:
                    pi_stacking.append({
                        "type": "pi_stacking",
                        "protein_residue": f'{ring[0]["resname"]}{ring[0]["residue_no"]}{ring[0]["chain"]}',
                        "centroid_distance": round(cd, 2),
                        "confidence": "potential",
                    })

    return {
        "hbonds": unique_hbonds[:20],
        "hydrophobic": unique_hydro[:20],
        "pi_stacking": pi_stacking[:5],
    }


# ── tool ─────────────────────────────────────────────────────────────────
class DockingTool(BaseTool):
    name = "docking"

    async def run(self, input: dict) -> dict:
        pdb_id = input.get("pdb_id", "").strip().upper()
        pdb_url = input.get("pdb_url", "").strip()
        smiles = input.get("smiles", "").strip()

        if not pdb_id and not pdb_url:
            return {"error": "pdb_id or pdb_url is required"}
        if not smiles:
            return {"error": "smiles is required"}

        # Self-heal missing binaries (obabel primarily via in-process pybel bindings)
        global VINA_CMD, OBABEL_CMD
        if not VINA_CMD or not os.path.isfile(VINA_CMD):
            found = shutil.which("vina")
            if found:
                VINA_CMD = found
            else:
                dest = os.path.join(tempfile.gettempdir(), "bin", "vina")
                dl = _download_vina(dest)
                if dl:
                    VINA_CMD = dl
        if not VINA_CMD:
            return {"error": "Dependencies missing: AutoDock Vina is not installed on the server and could not be downloaded."}

        tmpdir = tempfile.mkdtemp(prefix="docking_")
        try:
            # 1. Fetch PDB
            if not pdb_url:
                pdb_url = PDB_DOWNLOAD.format(pdb_id=pdb_id)
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(pdb_url)
                if r.status_code != 200:
                    return {"error": f"PDB not found at {pdb_url}"}
                pdb_content = r.text

            pdb_path = os.path.join(tmpdir, "protein.pdb")
            with open(pdb_path, "w") as f:
                f.write(pdb_content)

            # 2. Clean protein (strip waters, heteroatoms)
            cleaned = _clean_protein(pdb_content)
            clean_path = os.path.join(tmpdir, "cleaned.pdb")
            with open(clean_path, "w") as f:
                f.write(cleaned)

            # 3. Convert protein to PDBQT (in-process pybel → no subprocess, saves ~200+ MB)
            protein_pdbqt = os.path.join(tmpdir, "protein.pdbqt")
            if not _pdb_to_pdbqt_pybel(clean_path, protein_pdbqt):
                if not OBABEL_CMD:
                    OBABEL_CMD = _pip_install_obabel()
                if not OBABEL_CMD:
                    return {"error": "Open Babel not available – cannot prepare protein PDBQT."}
                proc = await asyncio.create_subprocess_exec(
                    OBABEL_CMD, clean_path, "-O", protein_pdbqt, "-xr",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode != 0 or not os.path.exists(protein_pdbqt):
                    err = stderr.decode() if stderr else "obabel failed"
                    return {"error": f"Protein PDBQT preparation failed: {err}"}

            # 4. Convert SMILES to 3D PDBQT (in-process pybel → no subprocess)
            ligand_pdbqt = os.path.join(tmpdir, "ligand.pdbqt")
            if not _smiles_to_pdbqt_pybel(smiles, ligand_pdbqt):
                if not OBABEL_CMD:
                    OBABEL_CMD = _pip_install_obabel()
                if not OBABEL_CMD:
                    return {"error": "Open Babel not available – cannot prepare ligand PDBQT."}
                proc = await asyncio.create_subprocess_exec(
                    OBABEL_CMD, f"-:{smiles}", "-O", ligand_pdbqt, "--gen3d", "-h",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode != 0 or not os.path.exists(ligand_pdbqt):
                    err = stderr.decode() if stderr else "obabel failed"
                    return {"error": f"Ligand PDBQT preparation failed: {err}"}

            # 5. Determine binding site box
            center = _find_ligand_center(pdb_content)
            if center:
                cx, cy, cz = center
                sx = sy = sz = 20
            else:
                cx, cy, cz = _find_protein_center(pdb_content)
                sx = sy = sz = 30

            # 6. Run Vina
            out_pdbqt = os.path.join(tmpdir, "out.pdbqt")
            vina_cmd = await asyncio.create_subprocess_exec(
                VINA_CMD,
                "--receptor", protein_pdbqt,
                "--ligand", ligand_pdbqt,
                "--out", out_pdbqt,
                "--center_x", str(cx),
                "--center_y", str(cy),
                "--center_z", str(cz),
                "--size_x", str(sx),
                "--size_y", str(sy),
                "--size_z", str(sz),
                "--exhaustiveness", "3",
                "--num_modes", "5",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(vina_cmd.communicate(), timeout=600)
            except asyncio.TimeoutError:
                vina_cmd.kill()
                await vina_cmd.communicate()
                return {"error": "Docking timed out after 10 minutes"}

            if vina_cmd.returncode != 0 or not os.path.exists(out_pdbqt):
                err = stderr.decode("utf-8", errors="replace")[:500] if stderr else ""
                return {"error": f"Vina failed (exit {vina_cmd.returncode}): {err}"}

            # 7. Parse results
            with open(out_pdbqt) as f:
                out_content = f.read()

            poses = _parse_vina_pdbqt(out_content)
            log = stdout.decode() if stdout else ""

            # 8. Run interaction fingerprinting on best pose
            interactions: dict[str, Any] = {"hbonds": [], "hydrophobic": [], "pi_stacking": []}
            ligand_pdb: str = ""
            if poses:
                best = poses[0]
                coords = best.get("coords", [])
                if coords:
                    ligand_pdb = _generate_ligand_pdb(coords)
                    interactions = _analyze_interactions(coords, cleaned)

            # 9. Build per-pose interaction summary
            pose_interactions: list[dict] = []
            for pose in poses:
                pc = pose.get("coords", [])
                if pc:
                    pi = _analyze_interactions(pc, cleaned)
                    pose_interactions.append({
                        "model": pose["model"],
                        "hbonds": len(pi.get("hbonds", [])),
                        "hydrophobic": len(pi.get("hydrophobic", [])),
                        "pi_stacking": len(pi.get("pi_stacking", [])),
                    })
                else:
                    pose_interactions.append({
                        "model": pose["model"],
                        "hbonds": 0,
                        "hydrophobic": 0,
                        "pi_stacking": 0,
                    })

            resolved_pdb_id = pdb_id or pdb_url.split("/")[-1].replace(".pdb", "").split("-")[0] if pdb_url else "predicted"
            return {
                "pdb_id": resolved_pdb_id,
                "smiles": smiles,
                "poses": poses,
                "num_poses": len(poses),
                "box_center": {"x": cx, "y": cy, "z": cz},
                "box_size": {"x": sx, "y": sy, "z": sz},
                "vina_log": log[:2000],
                "interactions": interactions,
                "pose_interactions": pose_interactions,
                "ligand_pdb": ligand_pdb,
                "from_cache": False,
            }

        except Exception as e:
            logger.exception("Docking run failed")
            return {"error": f"Docking failed: {e}"}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
