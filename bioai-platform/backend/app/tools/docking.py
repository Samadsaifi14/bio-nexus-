from __future__ import annotations

import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

# AutoDock Vina binary location
_VINA_BINARY: str | None = None
# FIX: was pointing at the Windows build (vina_1.2.3_win.exe) while the
# container runs Linux -> subprocess.run() failed with "Exec format error",
# which was being swallowed and recorded as a generic "failed" docking job.
_VINA_URL = "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.3/vina_1.2.3_linux_x86_64"
_EXE_NAME = "vina"

# Expected checksum for the Linux binary (from the GitHub release page).
# Fill this in from the release's checksums.txt / SHA256SUMS before deploying;
# left blank here since I can't fetch it in this sandbox. If left empty,
# verification is skipped (with a warning) rather than blocking startup.
_VINA_SHA256 = ""  # e.g. "a1b2c3..."


def _verify_checksum(path: Path) -> None:
    if not _VINA_SHA256:
        print("[docking] WARNING: _VINA_SHA256 not set, skipping binary verification.")
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
            f"Vina binary checksum mismatch (got {digest}, expected {_VINA_SHA256}). "
            "Refusing to use a possibly corrupted/tampered download."
        )


def _ensure_vina() -> str:
    """Download and locate the AutoDock Vina binary (Linux build)."""
    global _VINA_BINARY
    if _VINA_BINARY and os.path.isfile(_VINA_BINARY):
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


def smiles_to_pdbqt(smiles: str) -> str:
    """Convert SMILES to PDBQT via NCI CACTUS (3D SDF) + Open Babel."""
    import tempfile

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
    """
    Convert SDF to PDBQT.

    FIX: the previous implementation hand-appended a bare charge float onto
    raw PDB ATOM/HETATM lines. Real PDBQT requires AutoDock atom types
    (C, N, OA, HD, A, etc.) in a dedicated column, correct Gasteiger partial
    charges, and torsion tree info for the ligand. A hand-rolled line format
    is either rejected by Vina or silently mis-scored.

    We now shell out to Open Babel, which is purpose-built for this and is
    the tool the AutoDock docs themselves recommend for ligand prep.
    Requires `obabel` on PATH (add `openbabel` to the Dockerfile's apt-get
    install list, e.g. `apt-get install -y openbabel`).
    """
    pdbqt_path = sdf_path.rsplit(".", 1)[0] + ".pdbqt"
    try:
        result = subprocess.run(
            [
                "obabel",
                sdf_path,
                "-O", pdbqt_path,
                "--partialcharge", "gasteiger",
                "-p", "7.4",  # protonate at physiological pH
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
            "Open Babel (`obabel`) is not installed in this container. "
            "Add it to the Dockerfile, e.g.: RUN apt-get update && apt-get install -y openbabel"
        )
    finally:
        if os.path.isfile(pdbqt_path):
            os.unlink(pdbqt_path)


def make_pdb_from_sequence(sequence: str) -> str:
    """Create a minimal PDB file from amino acid sequence (Cα trace)."""
    lines = ["HEADER    PROTEIN STRUCTURE"]
    aa = "ACDEFGHIKLMNPQRSTVWY"

    for i, residue in enumerate(sequence.upper()):
        if residue in aa:
            x = i * 3.8  # ~3.8 Å per residue
            y = 2.0 * (i % 3) - 1.0
            z = 0.0
            atom_line = (
                f"ATOM  {i+1:5d}  CA  {residue} A{i+1:4d}    "
                f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"
            )
            lines.append(atom_line)

    lines.append("END")
    return "\n".join(lines)


def run_vina(
    protein_pdbqt: str | bytes,
    ligand_pdbqt: str,
    grid_center: list[float] = [0, 0, 0],
    grid_size: list[float] = [20, 20, 20],
    exhaustiveness: int = 8,
    num_modes: int = 9,
) -> dict:
    """Run AutoDock Vina and parse results."""
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

        affinity = None
        rmsd_lb = None
        rmsd_ub = None
        for line in result.stdout.split("\n"):
            if line.strip().startswith("1 "):
                parts = line.split()
                if len(parts) >= 4:
                    affinity = float(parts[1])
                    rmsd_lb = float(parts[2])
                    rmsd_ub = float(parts[3])

        return {
            "affinity": affinity,
            "rmsd_lb": rmsd_lb,
            "rmsd_ub": rmsd_ub,
            "result_sdf": output_pdbqt,
        }
