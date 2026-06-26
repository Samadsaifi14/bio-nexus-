import asyncio
import logging
import os
import re
import shutil
import tempfile
import time
from typing import Any

import httpx

from app.tools.base import BaseTool

logger = logging.getLogger(__name__)

PDB_DOWNLOAD = "https://files.rcsb.org/download/{pdb_id}.pdb"
VINA_CMD = shutil.which("vina") or "/usr/local/bin/vina"


def _find_ligand_center(pdb_content: str) -> tuple[float, float, float] | None:
    """Find the geometric center of the largest HETATM ligand (non-water)."""
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
    """Keep only ATOM records (protein), strip HETATM, waters, ANISOU, CONECT."""
    lines: list[str] = []
    for line in pdb_content.splitlines():
        if line.startswith("ATOM") and len(line) >= 54:
            lines.append(line)
        elif line.startswith("TER"):
            lines.append(line)
        elif line.startswith("END"):
            lines.append(line)
    return "\n".join(lines)


def _parse_vina_pdbqt(pdbqt: str) -> list[dict[str, Any]]:
    """Parse Vina output PDBQT into individual pose dicts."""
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
                        current_atoms.append({"x": x, "y": y, "z": z, "element": elem})
                    except ValueError:
                        continue
            if current_atoms:
                energy_match = re.search(r"REMARK VINA RESULT:\s*([-\d.]+)", chunk)
                poses.append({
                    "model": current_model,
                    "atoms": len(current_atoms),
                    "affinity": float(energy_match.group(1)) if energy_match else None,
                })
                current_atoms = []
    return poses


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

            # 3. Convert protein to PDBQT via obabel
            protein_pdbqt = os.path.join(tmpdir, "protein.pdbqt")
            proc = await asyncio.create_subprocess_exec(
                "obabel", clean_path, "-O", protein_pdbqt, "-xr",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0 or not os.path.exists(protein_pdbqt):
                err = stderr.decode() if stderr else "obabel failed"
                return {"error": f"Protein PDBQT preparation failed: {err}"}

            # 4. Convert SMILES to 3D PDBQT via obabel
            ligand_pdbqt = os.path.join(tmpdir, "ligand.pdbqt")
            proc = await asyncio.create_subprocess_exec(
                "obabel", f"-:{smiles}", "-O", ligand_pdbqt, "--gen3d", "-h",
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
                "--exhaustiveness", "8",
                "--num_modes", "9",
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

            resolved_pdb_id = pdb_id or pdb_url.split("/")[-1].replace(".pdb", "").split("-")[0] if pdb_url else "predicted"
            return {
                "pdb_id": resolved_pdb_id,
                "smiles": smiles,
                "poses": poses,
                "num_poses": len(poses),
                "box_center": {"x": cx, "y": cy, "z": cz},
                "box_size": {"x": sx, "y": sy, "z": sz},
                "vina_log": log[:2000],
                "from_cache": False,
            }

        except Exception as e:
            logger.exception("Docking run failed")
            return {"error": f"Docking failed: {e}"}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
