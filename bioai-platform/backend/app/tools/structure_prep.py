"""Structure preparation pipeline tools.

Pipeline: fetch → broken chain detection → SWISS-MODEL repair → PyMOL cleanup → fpocket → CASTp
"""

import asyncio
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FPOCKET_BIN = shutil.which("fpocket") or "/usr/local/bin/fpocket"
PYMOL_BIN = shutil.which("pymol") or "/usr/local/bin/pymol"
CASTPFOLD_BASE = "https://cfold.bme.uic.edu/castpfold"


# ── Step 1: Broken chain detection ───────────────────────────────────────────


@dataclass
class ChainHealth:
    has_missing_residues: bool = False
    missing_residue_count: int = 0
    missing_ranges: list[str] = field(default_factory=list)
    has_chain_breaks: bool = False
    chain_break_count: int = 0
    chain_breaks: list[dict] = field(default_factory=list)
    is_broken: bool = False
    chains: list[str] = field(default_factory=list)
    total_residues: int = 0


def detect_chain_health(pdb_text: str) -> ChainHealth:
    """Detect broken chains: missing residues (REMARK 465) + CA-CA distance gaps."""
    health = ChainHealth()

    # --- Parse REMARK 465 (missing residues) ---
    remark_lines = [
        line for line in pdb_text.splitlines()
        if line.startswith("REMARK 465")
    ]
    missing_pattern = re.compile(
        r"REMARK 465\s+(\S+)\s+(\S+)\s+(\d+)([A-Z]?)\s+(\d+)\s*([A-Z]?)"
    )
    for line in remark_lines:
        m = missing_pattern.match(line)
        if m:
            resname = m.group(1)
            chain_id = m.group(3) or " "
            resnum = int(m.group(5))
            health.missing_residue_count += 1
            health.missing_ranges.append(
                f"{chain_id.strip() or ' '}{resnum}{resname}"
            )

    health.has_missing_residues = health.missing_residue_count > 0

    # --- CA-CA distance check ---
    from Bio.PDB import PDBParser

    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("pdb", io.StringIO(pdb_text))

    model = structure[0]
    health.chains = [c.id for c in model]

    for chain in model:
        ca_atoms = [
            res["CA"]
            for res in chain
            if res.id[0] == " " and "CA" in res
        ]
        ca_atoms.sort(key=lambda a: a.parent.id[1])
        health.total_residues += len(ca_atoms)

        for i in range(1, len(ca_atoms)):
            prev = ca_atoms[i - 1]
            curr = ca_atoms[i]
            dist = (prev.coord - curr.coord).tolist()
            dist_val = (dist[0] ** 2 + dist[1] ** 2 + dist[2] ** 2) ** 0.5
            if dist_val > 4.2:
                health.has_chain_breaks = True
                health.chain_break_count += 1
                health.chain_breaks.append({
                    "chain": chain.id,
                    "from_resnum": ca_atoms[i - 1].parent.id[1],
                    "to_resnum": ca_atoms[i].parent.id[1],
                    "distance": round(dist_val, 2),
                })

    health.is_broken = health.has_missing_residues or health.has_chain_breaks
    return health


# ── Step 2: SWISS-MODEL repair ───────────────────────────────────────────────

SMR_REPO = "https://swissmodel.expasy.org/repository"


async def swissmodel_fetch_structures(accession: str) -> dict:
    """Fetch available structures from SMR Repository for a UniProt accession."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{SMR_REPO}/uniprot/{accession}.json")
        if resp.status_code == 404:
            return {"models": [], "experimental": []}
        resp.raise_for_status()
        data = resp.json()

    result = data.get("result", {})
    structures = result.get("structures", [])

    models = []
    experimental = []
    for s in structures:
        entry = {
            "template": s.get("template"),
            "method": s.get("method"),
            "coverage": s.get("coverage"),
            "coordinates_url": s.get("coordinates"),
        }
        if s.get("provider") == "PDB":
            experimental.append(entry)
        else:
            models.append(entry)

    return {"models": models, "experimental": experimental, "sequence": result.get("sequence", "")}


async def swissmodel_fetch_pdb(template: str) -> str | None:
    """Fetch PDB coordinates from SMR for a template ID."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{SMR_REPO}/templates/{template}.pdb")
            if resp.status_code == 200 and len(resp.text) > 50:
                return resp.text
    except Exception:
        pass
    return None


# ── Step 3: PyMOL cleanup ────────────────────────────────────────────────────


def pymol_cleanup(pdb_text: str) -> str:
    """Remove waters, hetero atoms, and add hydrogens using PyMOL.

    Falls back to Biopython stripping if PyMOL is not available.
    """
    if os.path.exists(PYMOL_BIN):
        return _pymol_cleanup_binary(pdb_text)
    return _biopython_cleanup(pdb_text)


def _pymol_cleanup_binary(pdb_text: str) -> str:
    """Use PyMOL binary for structure cleanup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = Path(tmpdir) / "input.pdb"
        out_path = Path(tmpdir) / "clean.pdb"
        in_path.write_text(pdb_text)

        cmd = [
            PYMOL_BIN,
            "-c",  # command-line mode
            "-q",  # quiet
            "-d", f"load {in_path}; remove resn HOH; remove hetatm; save {out_path}, enabled",
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=30, check=True)
            if out_path.exists():
                result = out_path.read_text()
                if len(result) > 100:
                    return result
        except Exception as e:
            logger.warning("PyMOL cleanup failed, falling back to Biopython: %s", e)

    return _biopython_cleanup(pdb_text)


def _biopython_cleanup(pdb_text: str) -> str:
    """Strip waters/hetero atoms using Biopython (fallback)."""
    from Bio.PDB import PDBParser, PDBIO, Select

    class ProteinSelect(Select):
        def accept_residue(self, res):
            return res.id[0] == " "

    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("pdb", io.StringIO(pdb_text))

    io_buf = io.BytesIO()
    pdb_io = PDBIO()
    pdb_io.set_structure(structure)
    pdb_io.save(io_buf, ProteinSelect())
    return io_buf.getvalue().decode("utf-8")


# ── Step 4: fpocket (local binary) ───────────────────────────────────────────


@dataclass
class FpocketResult:
    pocket_count: int = 0
    pockets: list[dict] = field(default_factory=list)
    raw_output: str = ""


def run_fpocket(pdb_text: str, probe_radius: float = 1.4) -> FpocketResult:
    """Run fpocket on PDB text. Returns pocket data."""
    if not os.path.exists(FPOCKET_BIN):
        logger.warning("fpocket binary not found at %s", FPOCKET_BIN)
        return FpocketResult(raw_output="fpocket not installed")

    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = Path(tmpdir) / "input.pdb"
        in_path.write_text(pdb_text)

        try:
            result = subprocess.run(
                [FPOCKET_BIN, "-f", str(in_path), "-r", str(probe_radius)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            fpocket_out = Path(tmpdir) / "input_out"
            return _parse_fpocket_output(fpocket_out, result.stdout + result.stderr)
        except subprocess.TimeoutExpired:
            return FpocketResult(raw_output="fpocket timed out")
        except Exception as e:
            return FpocketResult(raw_output=f"fpocket error: {e}")


def _parse_fpocket_output(out_dir: Path, raw_output: str) -> FpocketResult:
    """Parse fpocket output directory for pocket information."""
    result = FpocketResult(raw_output=raw_output)

    info_file = out_dir / "info" / "infos.txt"
    if not info_file.exists():
        return result

    try:
        text = info_file.read_text()
        pockets = []
        current_pocket: dict[str, Any] = {}

        for line in text.splitlines():
            line = line.strip()
            if line.startswith("Pocket"):
                if current_pocket:
                    pockets.append(current_pocket)
                pocket_id_match = re.search(r"Pocket\s+(\d+)", line)
                current_pocket = {
                    "id": int(pocket_id_match.group(1)) if pocket_id_match else len(pockets) + 1,
                    "druggability_score": 0.0,
                    "volume": 0.0,
                    "area": 0.0,
                    "score": 0.0,
                    "num_residues": 0,
                }
            elif "Druggability Score" in line:
                m = re.search(r":\s*([\d.]+)", line)
                if m:
                    current_pocket["druggability_score"] = float(m.group(1))
            elif "Volume" in line:
                m = re.search(r":\s*([\d.]+)", line)
                if m:
                    current_pocket["volume"] = float(m.group(1))
            elif "Area" in line:
                m = re.search(r":\s*([\d.]+)", line)
                if m:
                    current_pocket["area"] = float(m.group(1))
            elif "Score" in line and "Drug" not in line:
                m = re.search(r":\s*([\d.]+)", line)
                if m:
                    current_pocket["score"] = float(m.group(1))
            elif "Number of residues" in line:
                m = re.search(r":\s*(\d+)", line)
                if m:
                    current_pocket["num_residues"] = int(m.group(1))

        if current_pocket:
            pockets.append(current_pocket)

        result.pockets = pockets
        result.pocket_count = len(pockets)
    except Exception as e:
        logger.warning("Failed to parse fpocket output: %s", e)

    return result


# ── Step 5: CASTp (remote async via CASTpFold) ──────────────────────────────


async def castp_submit(pdb_text: str, probe_radius: float = 1.4) -> dict:
    """Submit PDB to CASTpFold server for pocket analysis."""
    async with httpx.AsyncClient(timeout=60) as client:
        files = {"pdb_file": ("structure.pdb", pdb_text.encode(), "text/plain")}
        data = {"radius": str(probe_radius)}
        resp = await client.post(f"{CASTPFOLD_BASE}/compute", files=files, data=data)
        resp.raise_for_status()
        text = resp.text
        job_match = re.search(r"result/([a-f0-9\-]+)", text) or re.search(
            r'job[_\-]?id["\s:=]+["\']?([a-f0-9\-]+)', text
        )
        if job_match:
            return {"job_id": job_match.group(1), "status": "submitted"}
        return {"status": "complete", "raw_html": text, "job_id": None}


async def castp_poll(job_id: str) -> dict:
    """Poll CASTpFold for job results."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{CASTPFOLD_BASE}/result/{job_id}")
        resp.raise_for_status()
        text = resp.text
        pockets = _parse_castp_html(text)
        if pockets:
            return {"status": "complete", "pockets": pockets}
        return {"status": "running"}


def _parse_castp_html(html: str) -> list[dict]:
    """Parse pocket data from CASTpFold result HTML."""
    pockets = []
    row_pattern = re.compile(
        r"<tr[^>]*>.*?<td[^>]*>\s*(\d+)\s*</td>"
        r".*?<td[^>]*>\s*([\d.]+)\s*</td>"
        r".*?<td[^>]*>\s*([\d.]+)\s*</td>.*?</tr>",
        re.DOTALL | re.IGNORECASE,
    )
    for m in row_pattern.finditer(html):
        pockets.append({
            "id": int(m.group(1)),
            "area_sa": float(m.group(2)),
            "volume_sa": float(m.group(3)),
        })
    return pockets


# ── Pipeline orchestrator ────────────────────────────────────────────────────


async def fetch_pdb_text(pdb_id: str) -> str:
    """Fetch PDB from RCSB."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
        )
        resp.raise_for_status()
        return resp.text
