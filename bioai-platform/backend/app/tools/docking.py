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
_IS_WINDOWS = os.name == "nt"
if _IS_WINDOWS:
    _VINA_URL = "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.7/vina_1.2.7_win.exe"
else:
    _VINA_URL = "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.7/vina_1.2.7_linux_x86_64"
_EXE_NAME = "vina.exe" if _IS_WINDOWS else "vina"
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


_OBABEL_BINARY: str | None = None


def _ensure_obabel() -> str:
    """Locate the Open Babel (`obabel`) binary.

    Checks PATH first (Linux/Docker), then the current Python interpreter's
    directory (Windows venvs keep `obabel.exe` in ``Scripts/`` next to
    ``python.exe``, which is not on PATH when uvicorn is launched via the
    interpreter directly).
    """
    global _OBABEL_BINARY
    if _OBABEL_BINARY and os.path.isfile(_OBABEL_BINARY):
        return _OBABEL_BINARY

    import shutil
    import sys

    candidates: list[str] = []
    which = shutil.which("obabel")
    if which:
        candidates.append(which)
    exe_dir = Path(sys.executable).resolve().parent
    for name in ("obabel.exe", "obabel", "obabel.bat"):
        candidates.append(str(exe_dir / name))

    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            _OBABEL_BINARY = candidate
            return _OBABEL_BINARY

    raise RuntimeError(
        "Open Babel (`obabel`) is not installed. "
        "Install it (e.g. `pip install openbabel-wheel` on Windows, or "
        "`RUN apt-get update && apt-get install -y openbabel` in the Dockerfile)."
    )


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
                _ensure_obabel(),
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
        raise RuntimeError(_ensure_obabel())
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
                _ensure_obabel(),
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

        # Flatten to a single rigid model. Open Babel wraps each chain of a
        # multi-chain/NMR structure in MODEL/ENDMDL blocks, and Vina rejects
        # multi-model rigid receptors ("Unexpected multi-MODEL tag found in
        # rigid receptor"). Dropping the block markers keeps every atom as one
        # receptor. TORSDOF/ROOT/BRANCH markers are dropped too so the output
        # is always a plain rigid receptor.
        flattened = "\n".join(
            l for l in content.splitlines()
            if not l.startswith(("MODEL", "ENDMDL", "ROOT", "ENDROOT",
                                 "BRANCH", "ENDBRANCH", "TORSDOF"))
        )
        return flattened
    except FileNotFoundError:
        raise RuntimeError(_ensure_obabel())
    finally:
        if in_path and os.path.isfile(in_path):
            os.unlink(in_path)
        if out_path and os.path.isfile(out_path):
            os.unlink(out_path)


# ---------------------------------------------------------------------------
# Vina execution + multi-pose parsing
# ---------------------------------------------------------------------------

_VINA_MODE_RE = re.compile(r"^\s*(\d+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s*$")
_GRID_CENTER_RE = re.compile(r"Grid center:\s*X\s+(-?[\d.]+)\s+Y\s+(-?[\d.]+)\s+Z\s+(-?[\d.]+)")
_GRID_SIZE_RE = re.compile(r"Grid size\s*:\s*X\s+(-?[\d.]+)\s+Y\s+(-?[\d.]+)\s+Z\s+(-?[\d.]+)")


def parse_vina_log(vina_log: str) -> dict:
    """Parse AutoDock Vina 1.2.x stdout into structured metadata + mode table.

    Handles the literal Vina 1.2.7 header layout:

        AutoDock Vina v1.2.7
        Grid center: X 2 Y 2 Z 2
        Grid size  : X 20 Y 20 Z 20
        Exhaustiveness: 8
        Performing docking (random seed: 1431381492) ...
        mode |   affinity | dist from best mode
             | (kcal/mol) | rmsd l.b.| rmsd u.b.
        -----+------------+----------+----------
           1            0          0          0
           2            0      6.008      8.028
    """
    version = ""
    grid_center: list[float] = []
    grid_size: list[float] = []
    exhaustiveness: int | None = None
    random_seed: int | None = None
    modes: list[dict] = []

    in_table = False
    for line in vina_log.splitlines():
        if not version:
            m = re.match(r"AutoDock Vina v([0-9.]+)", line)
            if m:
                version = m.group(1)

        m = _GRID_CENTER_RE.match(line)
        if m:
            grid_center = [float(m.group(1)), float(m.group(2)), float(m.group(3))]
            continue
        m = _GRID_SIZE_RE.match(line)
        if m:
            grid_size = [float(m.group(1)), float(m.group(2)), float(m.group(3))]
            continue
        m = re.match(r"Exhaustiveness:\s+(\d+)", line)
        if m:
            exhaustiveness = int(m.group(1))
            continue
        m = re.search(r"random seed:\s+(-?\d+)", line)
        if m:
            random_seed = int(m.group(1))
            continue

        if re.match(r"^\s*-{5,}", line):
            in_table = True
            continue
        if in_table:
            m = _VINA_MODE_RE.match(line)
            if m:
                modes.append({
                    "model": int(m.group(1)),
                    "affinity": float(m.group(2)),
                    "rmsd_lb": float(m.group(3)),
                    "rmsd_ub": float(m.group(4)),
                })
            else:
                in_table = False

    return {
        "vina_version": version,
        "grid_center": grid_center,
        "grid_size": grid_size,
        "exhaustiveness": exhaustiveness,
        "random_seed": random_seed,
        "modes": modes,
    }


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
        parsed = parse_vina_log(vina_log)
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
            "vina_version": parsed.get("vina_version", ""),
            "vina_meta": parsed,
            "ligand_pdb": ligand_pdb,
            "result_sdf": output_pdbqt,
        }


def _parse_vina_poses(output_pdbqt: str, vina_log: str) -> list[dict]:
    """Parse Vina output PDBQT into a list of per-pose dicts.

    Affinity + RMSD (l.b./u.b.) come from the scored mode table in the log;
    atom counts come from the multi-model output PDBQT.
    """
    parsed = parse_vina_log(vina_log)
    mode_table = {m["model"]: m for m in parsed["modes"]}

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
        atom_lines = [l for l in models[model_id] if l.startswith("HETATM") or l.startswith("ATOM")]
        atom_count = len(atom_lines)
        hydrogen_count = sum(
            1 for l in atom_lines
            if (l.split()[2].startswith("H") if len(l.split()) > 2 else False)
        )
        entry = mode_table.get(model_id, {})
        poses.append({
            "model": model_id,
            "atoms": atom_count,
            "hydrogens": hydrogen_count,
            "affinity": entry.get("affinity"),
            "rmsd_lb": entry.get("rmsd_lb"),
            "rmsd_ub": entry.get("rmsd_ub"),
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
