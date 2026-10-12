"""Pocket/cavity analysis with method-specific provenance.

CASTp, fpocket and the BioNexus SASA/geometric heuristic are deliberately
separate methods. No method silently substitutes values into another method's
label or fields.
"""

from __future__ import annotations

import asyncio
import io
import logging
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)
FPOCKET_BIN = "/usr/local/bin/fpocket"


class PocketAnalysisError(RuntimeError):
    pass


async def analyze_pockets_pdb_id(pdb_id: str, probe_radius: float = 1.4, method: str = "fpocket") -> dict:
    pdb_text = await _fetch_pdb(pdb_id)
    return await analyze_pockets_pdb_text(pdb_text, pdb_id, probe_radius, method=method)


async def analyze_pockets_pdb_text(
    pdb_text: str,
    pdb_id: str = "custom",
    probe_radius: float = 1.4,
    method: str = "fpocket",
) -> dict:
    return await _analyze_pockets(pdb_text, pdb_id, probe_radius, method=method)


async def _fetch_pdb(pdb_id: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb")
        response.raise_for_status()
        return response.text


async def _analyze_pockets(pdb_text: str, pdb_id: str, probe_radius: float, method: str = "fpocket") -> dict:
    method_key = (method or "fpocket").strip().lower().replace("-", "_")

    if method_key in {"castp", "castp3"}:
        result = _empty_result(
            pdb_id,
            probe_radius,
            method="CASTp",
            status="FAILED",
            engine_version="not-integrated",
            evidence_class="Unsupported/insufficient evidence",
            reason=(
                "Genuine CASTp result retrieval/execution is not integrated in this deployment. "
                "fpocket or the BioNexus heuristic must be selected explicitly; their values are never returned as CASTp output."
            ),
        )
        _attach_structure_summary(pdb_text, result)
        return result

    if method_key in {"fpocket", "f_pocket"}:
        fpocket = FPOCKET_BIN if Path(FPOCKET_BIN).exists() else (shutil.which("fpocket") or "")
        if not fpocket or not Path(fpocket).exists():
            if not _parse_pdb_chains(pdb_text)["chains"]:
                result = _empty_result(
                    pdb_id,
                    probe_radius,
                    method="fpocket",
                    status="FAILED",
                    engine_version="unavailable",
                    evidence_class="Unsupported/insufficient evidence",
                    reason="fpocket executable is unavailable; no heuristic was substituted",
                )
                _attach_structure_summary(pdb_text, result)
                return result
            methods_tried = [{"method": "fpocket", "status": "unavailable"}]
            try:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, _analyze_pockets_sasa_sync, pdb_text, pdb_id, probe_radius)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                methods_tried.append({"method": "sasa_heuristic", "status": "crashed"})
                result = _empty_result(
                    pdb_id,
                    probe_radius,
                    method="none",
                    status="FAILED",
                    engine_version="fpocket unavailable; sasa_heuristic crashed",
                    evidence_class="Unsupported/insufficient evidence",
                    reason=error,
                )
                result["methods_tried"] = methods_tried
                result["fallback_used"] = True
                result["fallback_method"] = "sasa_heuristic"
                result["error"] = str(exc)
                _attach_structure_summary(pdb_text, result)
                return result
            heuristic_status = "ran_no_pockets" if not result.get("pockets") else "ran_with_pockets"
            methods_tried.append({"method": "sasa_heuristic", "status": heuristic_status})
            result["method"] = "sasa_heuristic"
            result["engine"] = "BioNexus exploratory SASA heuristic"
            result["status"] = "DEGRADED"
            result["methods_tried"] = methods_tried
            result["fallback_used"] = True
            result["fallback_method"] = "sasa_heuristic"
            result["note"] = (
                "CASTp architecture: fpocket is unavailable in this deployment, so the "
                "analysis fell back to the BioNexus exploratory SASA heuristic. All "
                "values are attributed to sasa_heuristic; no fpocket or CASTp values "
                "were substituted."
            )
            _attach_structure_summary(pdb_text, result)
            return result
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _run_fpocket_analysis, fpocket, pdb_text, pdb_id, probe_radius)
        result.setdefault("fallback_used", False)
        result["methods_tried"] = [{"method": "fpocket", "status": "ok"}]
        return result

    if method_key in {"heuristic", "sasa", "sasa_heuristic", "bionexus_heuristic"}:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _analyze_pockets_sasa_sync, pdb_text, pdb_id, probe_radius)
        _attach_structure_summary(pdb_text, result)
        return result

    raise PocketAnalysisError("method must be one of: CASTp, fpocket, sasa_heuristic")


def _fpocket_version(fpocket_bin: str) -> str:
    for args in ([fpocket_bin, "-v"], [fpocket_bin, "--version"]):
        try:
            completed = subprocess.run(args, capture_output=True, text=True, timeout=10)
            text = (completed.stdout or completed.stderr or "").strip()
            if text:
                return text.splitlines()[0][:120]
        except Exception:
            continue
    return "unknown"


def _run_fpocket_analysis(fpocket_bin: str, pdb_text: str, pdb_id: str, probe_radius: float) -> dict:
    version = _fpocket_version(fpocket_bin)
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input.pdb"
        input_path.write_text(pdb_text, encoding="utf-8")
        try:
            completed = subprocess.run(
                [fpocket_bin, "-f", str(input_path), "-r", str(probe_radius)],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return _empty_result(
                pdb_id, probe_radius, method="fpocket", status="FAILED", engine_version=version,
                evidence_class="Unsupported/insufficient evidence", reason="fpocket timed out",
            )
        except Exception as exc:
            return _empty_result(
                pdb_id, probe_radius, method="fpocket", status="FAILED", engine_version=version,
                evidence_class="Unsupported/insufficient evidence", reason=f"fpocket execution failed: {type(exc).__name__}",
            )
        if completed.returncode != 0:
            return _empty_result(
                pdb_id, probe_radius, method="fpocket", status="FAILED", engine_version=version,
                evidence_class="Unsupported/insufficient evidence",
                reason=f"fpocket exited with code {completed.returncode}",
            )
        result = _parse_fpocket(Path(tmpdir) / "input_out", pdb_id, probe_radius, version)
        if not result["pockets"]:
            result["status"] = "FAILED"
            result["validation"] = {
                "reason": "fpocket emitted no parseable pockets",
                "scientific_processing_stopped": True,
                "castp_values_substituted": False,
            }
            result["evidence_class"] = "Unsupported/insufficient evidence"
        return result


def _extract_number(line: str) -> float | None:
    match = re.search(r":\s*(-?[\d.]+(?:[eE][+-]?\d+)?)", line)
    return float(match.group(1)) if match else None


def _parse_fpocket(out_dir: Path, pdb_id: str, probe_radius: float, version: str = "unknown") -> dict:
    info_candidates = [out_dir / "input_info.txt", out_dir / "info" / "infos.txt", out_dir / "infos.txt"]
    info_file = next((path for path in info_candidates if path.exists()), None)
    if info_file is None:
        return _empty_result(
            pdb_id, probe_radius, method="fpocket", status="FAILED", engine_version=version,
            evidence_class="Unsupported/insufficient evidence", reason="fpocket info file was not produced",
        )

    pockets: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in info_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        pocket_match = re.match(r"Pocket\s+(\d+)\s*:?", line)
        if pocket_match:
            if current:
                pockets.append(current)
            current = {
                "id": int(pocket_match.group(1)),
                "score": None,
                "druggability_score": None,
                "volume": None,
                "area": None,
                "alpha_spheres": None,
                "num_residues": 0,
                "residues": [],
                "centroid": [0.0, 0.0, 0.0],
            }
            continue
        if current is None:
            continue
        lower = line.lower()
        value = _extract_number(line)
        if value is None:
            continue
        if "druggability score" in lower:
            current["druggability_score"] = value
        elif "pocket score" in lower or ("score" in lower and "druggability" not in lower):
            current["score"] = value
        elif "volume" in lower:
            current["volume"] = value
        elif "surface area" in lower or "area" in lower:
            current["area"] = value
        elif "alpha sphere" in lower:
            current["alpha_spheres"] = int(round(value))
    if current:
        pockets.append(current)

    pockets_dir = out_dir / "pockets"
    for pocket in pockets:
        pocket_id = pocket["id"]
        atom_candidates = [pockets_dir / f"pocket{pocket_id}_atm.pdb", pockets_dir / f"pocket{pocket_id}_atm.pqr"]
        atom_file = next((path for path in atom_candidates if path.exists()), None)
        if atom_file:
            _enrich_pocket_from_pdb(pocket, atom_file)
        sphere_candidates = [pockets_dir / f"pocket{pocket_id}_vert.pqr", pockets_dir / f"pocket{pocket_id}_vert.pdb"]
        sphere_file = next((path for path in sphere_candidates if path.exists()), None)
        if sphere_file:
            pocket["alpha_spheres"] = sum(
                line.startswith(("ATOM", "HETATM"))
                for line in sphere_file.read_text(encoding="utf-8", errors="replace").splitlines()
            )

    public_pockets: list[dict[str, Any]] = []
    for pocket in pockets:
        volume = pocket.get("volume")
        radius = round((3 * volume / (4 * math.pi)) ** (1 / 3), 2) if isinstance(volume, (int, float)) and volume > 0 else 0.0
        public_pockets.append({
            "id": pocket["id"],
            "area_sa": round(float(pocket["area"]), 3) if pocket.get("area") is not None else 0.0,
            "volume_sa": round(float(volume), 3) if volume is not None else 0.0,
            "score": pocket.get("score"),
            "druggability_score": pocket.get("druggability_score"),
            "alpha_spheres": pocket.get("alpha_spheres"),
            "num_residues": int(pocket.get("num_residues") or 0),
            "residues": pocket.get("residues", []),
            "centroid": [round(float(value), 3) for value in pocket.get("centroid", [0.0, 0.0, 0.0])],
            "radius": radius,
            "method_metrics": {
                "fpocket_score": pocket.get("score"),
                "fpocket_druggability_score": pocket.get("druggability_score"),
                "fpocket_alpha_spheres": pocket.get("alpha_spheres"),
            },
        })

    return {
        "status": "VALID",
        "method": "fpocket",
        "engine_version": version,
        "fallback_used": False,
        "fallback_method": None,
        "evidence_class": "Deterministic computation",
        "validation": {"source": "fpocket native output", "castp_values_substituted": False},
        "pdb_id": pdb_id,
        "probe_radius": probe_radius,
        "total_residues": 0,
        "pockets": public_pockets,
    }


def _enrich_pocket_from_pdb(pocket: dict[str, Any], pdb_path: Path) -> None:
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    residues: list[str] = []
    seen: set[str] = set()
    for line in pdb_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        try:
            xs.append(float(line[30:38])); ys.append(float(line[38:46])); zs.append(float(line[46:54]))
        except ValueError:
            pass
        chain = line[21:22].strip() or "A"
        resname = line[17:20].strip()
        resseq = line[22:26].strip()
        label = f"{chain}{resseq}{resname}"
        if label not in seen:
            seen.add(label)
            residues.append(label)
    if xs:
        pocket["centroid"] = [sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs)]
    pocket["residues"] = residues
    pocket["num_residues"] = len(residues)


def _empty_result(
    pdb_id: str,
    probe_radius: float,
    total_residues: int = 0,
    *,
    method: str = "fpocket",
    status: str = "FAILED",
    engine_version: str = "unknown",
    evidence_class: str = "Unsupported/insufficient evidence",
    reason: str = "No result",
) -> dict:
    return {
        "status": status,
        "method": method,
        "engine_version": engine_version,
        "fallback_used": False,
        "fallback_method": None,
        "evidence_class": evidence_class,
        "validation": {
            "reason": reason,
            "scientific_processing_stopped": status == "FAILED",
            "castp_values_substituted": False,
        },
        "pdb_id": pdb_id,
        "probe_radius": probe_radius,
        "total_residues": total_residues,
        "pockets": [],
    }


def _analyze_pockets_sasa_sync(pdb_text: str, pdb_id: str, probe_radius: float) -> dict:
    from Bio.PDB import PDBParser, SASA

    parser = PDBParser(QUIET=True)
    structure = parser.get_structure(pdb_id, io.StringIO(pdb_text))
    sr = SASA.ShrakeRupley(probe_radius=probe_radius)
    sr.compute(structure[0], level="R")

    residues_sasa: list[dict[str, Any]] = []
    coords: list[tuple[float, float, float]] = []
    for chain in structure[0]:
        for residue in chain:
            if residue.id[0] != " ":
                continue
            ca = residue["CA"] if "CA" in residue else None
            if ca is None:
                continue
            residues_sasa.append({
                "chain": chain.id,
                "residue": residue.resname,
                "resnum": int(residue.id[1]),
                "sasa": round(float(getattr(residue, "sasa", 0.0)), 3),
                "coords": [round(float(value), 3) for value in ca.coord],
            })
            coords.append(tuple(float(value) for value in ca.coord))

    pockets = _detect_pockets_sasa(residues_sasa, coords, probe_radius)
    return {
        "status": "VALID",
        "method": "BioNexus exploratory SASA heuristic",
        "engine_version": "Biopython ShrakeRupley + BioNexus concave-packing heuristic v1",
        "fallback_used": False,
        "fallback_method": None,
        "evidence_class": "Heuristic",
        "validation": {
            "exploratory_geometric_estimate": True,
            "not_castp": True,
            "not_fpocket": True,
            "castp_values_substituted": False,
        },
        "pdb_id": pdb_id,
        "probe_radius": probe_radius,
        "total_residues": len(residues_sasa),
        "pockets": pockets,
    }


def _detect_pockets_sasa(residues: list[dict], coords: list[tuple], probe_radius: float) -> list[dict]:
    """Exploratory concave-packing detector; not CASTp or fpocket output."""
    if not residues:
        return []
    import numpy as np

    points = np.array(coords, dtype=float)
    if len(points) != len(residues):
        return []
    distances = np.linalg.norm(points[:, None] - points[None], axis=2)
    neighbors = (distances < 12.0).sum(axis=1) - 1
    sasas = np.array([float(residue["sasa"]) for residue in residues], dtype=float)
    surface = sasas > 8.0
    if not int(surface.sum()):
        return []
    exposure_cutoff = np.percentile(sasas[surface], 60)
    density_cutoff = np.percentile(neighbors, 60)
    lining = surface & (sasas < exposure_cutoff) & (neighbors >= density_cutoff)

    visited = np.zeros(len(residues), dtype=bool)
    clusters: list[list[int]] = []
    for start in np.where(lining)[0]:
        if visited[start]:
            continue
        stack = [int(start)]
        visited[start] = True
        cluster: list[int] = []
        while stack:
            current = stack.pop()
            cluster.append(current)
            for neighbor in np.where(lining & (distances[current] < 10.0))[0]:
                neighbor = int(neighbor)
                if not visited[neighbor]:
                    visited[neighbor] = True
                    stack.append(neighbor)
        if len(cluster) >= 4:
            clusters.append(cluster)
    clusters.sort(key=len, reverse=True)

    output: list[dict[str, Any]] = []
    for index, cluster in enumerate(clusters, start=1):
        cluster_residues = [residues[i] for i in cluster]
        cluster_points = points[cluster]
        centroid = cluster_points.mean(axis=0)
        max_distance = max(float(np.linalg.norm(point - centroid)) for point in cluster_points)
        radius = max_distance + probe_radius
        volume = (4.0 / 3.0) * math.pi * radius**3
        area_estimate = sum(float(residue["sasa"]) for residue in cluster_residues)
        output.append({
            "id": index,
            "area_sa": round(area_estimate, 3),
            "volume_sa": round(volume, 3),
            "score": None,
            "druggability_score": None,
            "alpha_spheres": None,
            "num_residues": len(cluster_residues),
            "residues": [f"{r['chain']}{r['resnum']}{r['residue']}" for r in cluster_residues],
            "centroid": [round(float(value), 3) for value in centroid],
            "radius": round(radius, 3),
            "method_metrics": {
                "heuristic_surface_area_estimate": round(area_estimate, 3),
                "heuristic_bounding_sphere_volume": round(volume, 3),
            },
        })
    return output


_PDB_AA = {
    "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F", "GLY": "G", "HIS": "H", "ILE": "I",
    "LYS": "K", "LEU": "L", "MET": "M", "ASN": "N", "PRO": "P", "GLN": "Q", "ARG": "R", "SER": "S",
    "THR": "T", "VAL": "V", "TRP": "W", "TYR": "Y", "MSE": "M",
}


def _parse_pdb_chains(pdb_text: str) -> dict[str, Any]:
    chain_residues: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, int, str]] = set()
    for line in pdb_text.splitlines():
        if not line.startswith("ATOM"):
            continue
        chain = line[21:22].strip() or "A"
        resname = line[17:20].strip().upper()
        try:
            resnum = int(line[22:26].strip())
        except ValueError:
            continue
        insertion_code = line[26:27].strip()
        key = (chain, resnum, insertion_code)
        if key in seen:
            continue
        seen.add(key)
        chain_residues.setdefault(chain, []).append({
            "num": resnum,
            "name": resname,
            "one": _PDB_AA.get(resname, "X"),
            "label": f"{chain}{resnum}{resname}",
        })

    chains: list[dict[str, Any]] = []
    residue_lookup: dict[tuple[str, int], dict[str, Any]] = {}
    for chain, residues in chain_residues.items():
        residues.sort(key=lambda item: item["num"])
        numbers = [item["num"] for item in residues]
        gaps: list[dict[str, int]] = []
        for left, right in zip(numbers, numbers[1:]):
            if right > left + 1:
                gaps.append({"start": left + 1, "end": right - 1, "count": right - left - 1})
        for residue in residues:
            residue_lookup[(chain, residue["num"])] = residue
        chains.append({
            "id": chain,
            "residue_count": len(residues),
            "sequence": "".join(item["one"] for item in residues),
            "gaps": gaps,
            "residues": residues,
        })
    return {"chains": chains, "residue_lookup": residue_lookup}


def _parse_pocket_label(label: str) -> tuple[str, int, str] | None:
    match = re.match(r"(.)(-?\d+)([A-Za-z]{3})$", label)
    if not match:
        return None
    return match.group(1), int(match.group(2)), match.group(3).upper()


def _attach_structure_summary(pdb_text: str, result: dict[str, Any]) -> None:
    parsed = _parse_pdb_chains(pdb_text)
    result["chains"] = parsed["chains"]
    result["total_residues"] = sum(chain["residue_count"] for chain in parsed["chains"])
    lookup = parsed["residue_lookup"]
    for pocket in result.get("pockets", []):
        details: list[dict[str, Any]] = []
        spans: dict[str, list[int]] = {}
        for label in pocket.get("residues", []):
            parsed_label = _parse_pocket_label(label)
            if parsed_label is None:
                continue
            chain, number, name = parsed_label
            residue = lookup.get((chain, number))
            details.append({
                "chain": chain,
                "residue_number": number,
                "residue_name": name,
                "one": residue["one"] if residue else _PDB_AA.get(name, "X"),
                "label": label,
                "coordinate_present": residue is not None,
            })
            spans.setdefault(chain, []).append(number)
        pocket["residue_details"] = details
        pocket["chain_spans"] = [
            {"chain": chain, "min": min(numbers), "max": max(numbers), "count": len(numbers)}
            for chain, numbers in spans.items() if numbers
        ]
        pocket["gap_ranges"] = [
            {"chain": chain["id"], "gaps": chain["gaps"]}
            for chain in parsed["chains"] if chain["id"] in spans and chain["gaps"]
        ]
