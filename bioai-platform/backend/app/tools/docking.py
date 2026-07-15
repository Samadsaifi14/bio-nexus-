from __future__ import annotations

import math
import os
import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

# AutoDock Vina binary location
_VINA_BINARY: str | None = None
_VINA_URL = "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.3/vina_1.2.3_linux_x86_64"
_EXE_NAME = "vina"
_VINA_SHA256 = ""


def _verify_checksum(path: Path) -> None:
    if not _VINA_SHA256:
        return
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    digest = h.hexdigest()
    if digest != _VINA_SHA256:
        path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Vina binary checksum mismatch (got {digest}, expected {_VINA_SHA256})."
        )


def _ensure_vina() -> str:
    """Locate the AutoDock Vina binary."""
    global _VINA_BINARY
    if _VINA_BINARY and os.path.isfile(_VINA_BINARY):
        return _VINA_BINARY

    import shutil
    for candidate in ["/usr/local/bin/vina", shutil.which("vina") or ""]:
        if candidate and os.path.isfile(candidate):
            _VINA_BINARY = candidate
            return _VINA_BINARY

    bin_dir = Path(tempfile.gettempdir()) / "vina_bin"
    bin_dir.mkdir(exist_ok=True)
    exe_path = bin_dir / _EXE_NAME

    if not exe_path.is_file():
        print(f"[docking] Downloading AutoDock Vina from {_VINA_URL} ...")
        urllib.request.urlretrieve(_VINA_URL, str(exe_path))
        _verify_checksum(exe_path)
        os.chmod(str(exe_path), 0o755)

    _VINA_BINARY = str(exe_path)
    return _VINA_BINARY


# ---------------------------------------------------------------------------
# PDB fetching
# ---------------------------------------------------------------------------

def fetch_pdb_from_rcsb(pdb_id: str) -> str:
    """Download a PDB file from RCSB by 4-character PDB ID."""
    pdb_id = pdb_id.strip().upper()
    if len(pdb_id) != 4:
        raise ValueError(f"Invalid PDB ID: {pdb_id!r}")
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    try:
        data = urllib.request.urlopen(url, timeout=30).read().decode("utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch PDB {pdb_id} from RCSB: {e}")
    if "ATOM" not in data and "HETATM" not in data:
        raise RuntimeError(f"PDB {pdb_id} from RCSB contains no coordinate data")
    return data


# ---------------------------------------------------------------------------
# Grid center computation
# ---------------------------------------------------------------------------

_ATOM_RE = re.compile(
    r"^(ATOM|HETATM)\s+\d+\s+\S+\s+(\S)\s+(\d+)\s+"
    r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"
)


def compute_grid_center(pdb_text: str) -> list[float]:
    """Compute the geometric centre of all ATOM (non-ligand) records."""
    xs, ys, zs = [], [], []
    for line in pdb_text.splitlines():
        if line.startswith("ATOM"):
            m = _ATOM_RE.match(line)
            if m:
                xs.append(float(m.group(4)))
                ys.append(float(m.group(5)))
                zs.append(float(m.group(6)))
    if not xs:
        return [0.0, 0.0, 0.0]
    return [sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs)]


# ---------------------------------------------------------------------------
# Ligand prep (SMILES -> PDBQT via NCI CACTUS + Open Babel)
# ---------------------------------------------------------------------------

def smiles_to_pdbqt(smiles: str) -> str:
    """Convert SMILES to PDBQT via NCI CACTUS (3D SDF) + Open Babel."""
    try:
        url = f"https://cactus.nci.nih.gov/chemical/structure/{smiles}/file?format=sdf&get3d=true"
        sdf_bytes = urllib.request.urlopen(url, timeout=30).read()
    except Exception as e:
        raise RuntimeError(f"Failed to get 3D structure from CACTUS: {e}")

    with tempfile.NamedTemporaryFile(suffix=".sdf", delete=False, mode="wb") as f:
        f.write(sdf_bytes)
        sdf_path = f.name

    try:
        return _sdf_to_pdbqt(sdf_path)
    finally:
        os.unlink(sdf_path)


def _sdf_to_pdbqt(sdf_path: str) -> str:
    """Convert SDF to PDBQT using Open Babel."""
    pdbqt_path = sdf_path.rsplit(".", 1)[0] + ".pdbqt"
    try:
        result = subprocess.run(
            [
                "obabel",
                sdf_path,
                "-O", pdbqt_path,
                "--partialcharge", "gasteiger",
                "-p", "7.4",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Open Babel ligand conversion failed: {result.stderr[:1000]}")
        if not os.path.isfile(pdbqt_path):
            raise RuntimeError("Open Babel did not produce a PDBQT output file")
        with open(pdbqt_path, "r") as f:
            content = f.read()
        if not content.strip():
            raise RuntimeError("PDBQT conversion produced empty output")
        return content
    except FileNotFoundError:
        raise RuntimeError(
            "Open Babel (`obabel`) is not installed. "
            "Add it to the Dockerfile: RUN apt-get update && apt-get install -y openbabel"
        )
    finally:
        if os.path.isfile(pdbqt_path):
            os.unlink(pdbqt_path)


# ---------------------------------------------------------------------------
# Receptor prep (PDB -> PDBQT rigid receptor)
# ---------------------------------------------------------------------------

def pdb_to_pdbqt_receptor(pdb_text: str) -> str:
    """Convert a plain PDB receptor to PDBQT (rigid, for Vina)."""
    in_path = None
    out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False, mode="w") as f:
            f.write(pdb_text)
            in_path = f.name
        out_path = in_path.rsplit(".", 1)[0] + ".pdbqt"

        result = subprocess.run(
            [
                "obabel",
                in_path,
                "-O", out_path,
                "-xr",
                "--partialcharge", "gasteiger",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Open Babel receptor conversion failed: {result.stderr[:1000]}")
        if not os.path.isfile(out_path):
            raise RuntimeError("Open Babel did not produce a receptor PDBQT output file")
        with open(out_path, "r") as f:
            content = f.read()
        if not content.strip():
            raise RuntimeError("Receptor PDBQT conversion produced empty output")
        return content
    except FileNotFoundError:
        raise RuntimeError(
            "Open Babel (`obabel`) is not installed. "
            "Add it to the Dockerfile: RUN apt-get update && apt-get install -y openbabel"
        )
    finally:
        if in_path and os.path.isfile(in_path):
            os.unlink(in_path)
        if out_path and os.path.isfile(out_path):
            os.unlink(out_path)


# ---------------------------------------------------------------------------
# Vina execution + multi-pose parsing
# ---------------------------------------------------------------------------

def run_vina(
    protein_pdbqt: str | bytes,
    ligand_pdbqt: str,
    grid_center: list[float] = [0, 0, 0],
    grid_size: list[float] = [20, 20, 20],
    exhaustiveness: int = 8,
    num_modes: int = 9,
) -> dict:
    """Run AutoDock Vina and return parsed multi-pose results."""
    vina_bin = _ensure_vina()

    with tempfile.TemporaryDirectory() as tmp:
        prot_path = os.path.join(tmp, "protein.pdbqt")
        if isinstance(protein_pdbqt, bytes):
            with open(prot_path, "wb") as f:
                f.write(protein_pdbqt)
        else:
            with open(prot_path, "w") as f:
                f.write(protein_pdbqt)

        lig_path = os.path.join(tmp, "ligand.pdbqt")
        with open(lig_path, "w") as f:
            f.write(ligand_pdbqt)

        out_path = os.path.join(tmp, "output.pdbqt")

        cmd = [
            vina_bin,
            "--receptor", prot_path,
            "--ligand", lig_path,
            "--center_x", str(grid_center[0]),
            "--center_y", str(grid_center[1]),
            "--center_z", str(grid_center[2]),
            "--size_x", str(grid_size[0]),
            "--size_y", str(grid_size[1]),
            "--size_z", str(grid_size[2]),
            "--exhaustiveness", str(exhaustiveness),
            "--num_modes", str(num_modes),
            "--out", out_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            raise RuntimeError(f"Vina failed: {result.stderr[:2000]}")

        with open(out_path, "r") as f:
            output_pdbqt = f.read()

        vina_log = result.stdout
        poses = _parse_vina_poses(output_pdbqt, vina_log)
        ligand_pdb = _extract_ligand_pdb(output_pdbqt)

        best_affinity = None
        if poses:
            best_affinity = poses[0]["affinity"]

        return {
            "poses": poses,
            "num_poses": len(poses),
            "affinity": best_affinity,
            "vina_log": vina_log,
            "ligand_pdb": ligand_pdb,
            "result_sdf": output_pdbqt,
        }


def _parse_vina_poses(output_pdbqt: str, vina_log: str) -> list[dict]:
    """Parse Vina output PDBQT into a list of per-pose dicts."""
    affinity_from_log: dict[int, float] = {}
    for line in vina_log.splitlines():
        m = re.match(r"\s*(\d+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", line)
        if m:
            mode = int(m.group(1))
            affinity_from_log[mode] = float(m.group(2))

    models: dict[int, list[str]] = {}
    current_model: int | None = None
    for line in output_pdbqt.splitlines():
        if line.startswith("MODEL"):
            parts = line.split()
            if len(parts) >= 2:
                current_model = int(parts[1])
                models[current_model] = []
        elif line.startswith("ENDMDL"):
            current_model = None
        elif current_model is not None:
            models.setdefault(current_model, []).append(line)

    poses = []
    for model_id in sorted(models.keys()):
        atom_count = sum(1 for l in models[model_id] if l.startswith("HETATM") or l.startswith("ATOM"))
        affinity = affinity_from_log.get(model_id, None)
        poses.append({
            "model": model_id,
            "atoms": atom_count,
            "affinity": affinity,
        })

    return poses


def _extract_ligand_pdb(output_pdbqt: str) -> str:
    """Extract HETATM lines from the best (first) model as PDB for 3D viewer."""
    in_model = False
    lines: list[str] = []
    for line in output_pdbqt.splitlines():
        if line.startswith("MODEL") and not in_model:
            in_model = True
            continue
        if line.startswith("ENDMDL"):
            break
        if in_model and (line.startswith("HETATM") or line.startswith("ATOM")):
            pdb_line = _pdbqt_line_to_pdb(line)
            lines.append(pdb_line)

    if not lines:
        return ""
    lines.append("END")
    return "\n".join(lines)


def _pdbqt_line_to_pdb(pdbqt_line: str) -> str:
    """Convert a PDBQT ATOM/HETATM line to a standard PDB ATOM/HETATM line."""
    fields = pdbqt_line.split()
    if len(fields) < 7:
        return pdbqt_line
    record = fields[0]
    atom_num = fields[1]
    atom_name = fields[2]
    res_name = fields[3]
    chain = fields[4] if len(fields[4]) == 1 and fields[4].isalpha() else "A"
    res_seq = fields[5]
    x = float(fields[6])
    y = float(fields[7])
    z = float(fields[8]) if len(fields) > 8 else 0.0

    return (
        f"{record:<6}{atom_num:>5s}  {atom_name:<4s}{res_name:<3s} "
        f"{chain}{res_seq:>4s}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           "
    )
