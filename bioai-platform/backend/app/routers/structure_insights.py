"""Research-grade structural insight endpoints.

Computes deterministic geometry directly from PDB coordinates. Electrostatic
patches use residue formal-charge classes and are explicitly labelled as a
heuristic, not a Poisson-Boltzmann/APBS calculation.
"""
from __future__ import annotations

import io
import math
from typing import Optional

import httpx
from Bio.PDB import PDBParser, ShrakeRupley
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/structure_insights", tags=["structure-insights"])

CHARGED = {"ASP": -1, "GLU": -1, "LYS": 1, "ARG": 1, "HIS": 1}
AA1 = {"ALA":"A","ARG":"R","ASN":"N","ASP":"D","CYS":"C","GLN":"Q","GLU":"E","GLY":"G","HIS":"H","ILE":"I","LEU":"L","LYS":"K","MET":"M","PHE":"F","PRO":"P","SER":"S","THR":"T","TRP":"W","TYR":"Y","VAL":"V"}


class MutationRequest(BaseModel):
    pdb_id: str = Field(..., min_length=4, max_length=32)
    chain: str = Field("A", min_length=1, max_length=4)
    residue_number: int
    alternate: str = Field(..., min_length=1, max_length=3)


async def _fetch(pdb_id: str) -> str:
    ident = pdb_id.upper()
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.get(f"https://files.rcsb.org/download/{ident}.pdb")
    if response.status_code != 200 or "ATOM" not in response.text:
        raise HTTPException(404, f"PDB not found or has no ATOM records: {ident}")
    return response.text


def _structure(pdb_text: str):
    return PDBParser(QUIET=True).get_structure("structure", io.StringIO(pdb_text))


def _residue_records(structure, chain: Optional[str] = None) -> list[dict]:
    rows = []
    model = structure[0]
    for ch in model:
        if chain and ch.id != chain:
            continue
        for residue in ch:
            if residue.id[0] != " ":
                continue
            if "CA" not in residue:
                continue
            coord = residue["CA"].coord
            rows.append({
                "chain": ch.id,
                "resnum": int(residue.id[1]),
                "icode": str(residue.id[2]).strip(),
                "resname": residue.resname,
                "aa": AA1.get(residue.resname, "X"),
                "coord": [float(coord[0]), float(coord[1]), float(coord[2])],
                "residue": residue,
            })
    return rows


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x-y) ** 2 for x, y in zip(a, b)))


def contact_map(pdb_text: str, chain: Optional[str] = None, cutoff: float = 8.0) -> dict:
    rows = _residue_records(_structure(pdb_text), chain)
    contacts = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            d = _distance(rows[i]["coord"], rows[j]["coord"])
            if d <= cutoff:
                contacts.append({
                    "a": {k: rows[i][k] for k in ("chain","resnum","icode","resname","aa")},
                    "b": {k: rows[j][k] for k in ("chain","resnum","icode","resname","aa")},
                    "distance_angstrom": round(d, 3),
                })
    return {"cutoff_angstrom": cutoff, "residue_count": len(rows), "contact_count": len(contacts), "contacts": contacts}


def interface_analysis(pdb_text: str, cutoff: float = 5.0) -> dict:
    rows = _residue_records(_structure(pdb_text))
    interfaces: dict[tuple[str,str], dict] = {}
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if rows[i]["chain"] == rows[j]["chain"]:
                continue
            d = _distance(rows[i]["coord"], rows[j]["coord"])
            if d > cutoff:
                continue
            pair = tuple(sorted((rows[i]["chain"], rows[j]["chain"])))
            rec = interfaces.setdefault(pair, {"chains": list(pair), "contact_count": 0, "residues": set(), "min_distance_angstrom": None})
            rec["contact_count"] += 1
            rec["residues"].add(f"{rows[i]['chain']}:{rows[i]['resname']}{rows[i]['resnum']}")
            rec["residues"].add(f"{rows[j]['chain']}:{rows[j]['resname']}{rows[j]['resnum']}")
            rec["min_distance_angstrom"] = d if rec["min_distance_angstrom"] is None else min(rec["min_distance_angstrom"], d)
    out = []
    for rec in interfaces.values():
        rec["residues"] = sorted(rec["residues"])
        rec["interface_residue_count"] = len(rec["residues"])
        rec["min_distance_angstrom"] = round(rec["min_distance_angstrom"], 3)
        out.append(rec)
    return {"cutoff_angstrom": cutoff, "interfaces": sorted(out, key=lambda x: x["contact_count"], reverse=True)}


def surface_analysis(pdb_text: str, chain: Optional[str] = None) -> dict:
    structure = _structure(pdb_text)
    try:
        ShrakeRupley().compute(structure, level="R")
    except Exception as exc:
        raise ValueError(f"surface calculation failed: {exc}") from exc
    residues = []
    total = 0.0
    for row in _residue_records(structure, chain):
        sasa = float(getattr(row["residue"], "sasa", 0.0) or 0.0)
        total += sasa
        residues.append({
            "chain": row["chain"], "resnum": row["resnum"], "resname": row["resname"],
            "sasa_angstrom2": round(sasa, 3), "formal_charge_class": CHARGED.get(row["resname"], 0),
        })
    charged_sasa = sum(r["sasa_angstrom2"] for r in residues if r["formal_charge_class"] != 0)
    positive = sum(r["sasa_angstrom2"] for r in residues if r["formal_charge_class"] > 0)
    negative = sum(r["sasa_angstrom2"] for r in residues if r["formal_charge_class"] < 0)
    return {
        "method": "Bio.PDB ShrakeRupley",
        "total_sasa_angstrom2": round(total, 3),
        "charged_residue_sasa_angstrom2": round(charged_sasa, 3),
        "charge_patch_heuristic": {
            "method": "formal residue charge class weighted by residue SASA",
            "positive_exposed_area_angstrom2": round(positive, 3),
            "negative_exposed_area_angstrom2": round(negative, 3),
            "net_exposed_charge_area_index": round(positive-negative, 3),
            "evidence_class": "Heuristic",
            "limitation": "Not an electrostatic potential calculation; use APBS/Poisson-Boltzmann for physical electrostatic surfaces.",
        },
        "residues": residues,
    }


def mutation_context(pdb_text: str, chain: str, residue_number: int, alternate: str, radius: float = 8.0) -> dict:
    rows = _residue_records(_structure(pdb_text))
    target = next((r for r in rows if r["chain"] == chain and r["resnum"] == residue_number), None)
    if not target:
        raise ValueError(f"residue {chain}:{residue_number} not found")
    neighbours = []
    for row in rows:
        if row is target:
            continue
        d = _distance(target["coord"], row["coord"])
        if d <= radius:
            neighbours.append({
                "chain": row["chain"], "resnum": row["resnum"], "resname": row["resname"],
                "distance_angstrom": round(d, 3),
            })
    return {
        "mutation": f"{target['aa']}{residue_number}{alternate.upper()}",
        "chain": chain,
        "reference_residue": target["resname"],
        "alternate": alternate.upper(),
        "mapping_status": "mapped",
        "neighbour_radius_angstrom": radius,
        "neighbours": sorted(neighbours, key=lambda n: n["distance_angstrom"]),
        "interpretation": "Geometric context only. No energetic or pathogenicity effect is inferred from proximity alone.",
    }


@router.get("/{pdb_id}/contacts")
async def contacts(pdb_id: str, chain: Optional[str] = None, cutoff: float = Query(8.0, ge=3.0, le=15.0)):
    return contact_map(await _fetch(pdb_id), chain, cutoff)


@router.get("/{pdb_id}/interfaces")
async def interfaces(pdb_id: str, cutoff: float = Query(5.0, ge=3.0, le=10.0)):
    return interface_analysis(await _fetch(pdb_id), cutoff)


@router.get("/{pdb_id}/surface")
async def surface(pdb_id: str, chain: Optional[str] = None):
    try:
        return surface_analysis(await _fetch(pdb_id), chain)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/mutation")
async def mutation(body: MutationRequest):
    try:
        return mutation_context(await _fetch(body.pdb_id), body.chain, body.residue_number, body.alternate)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
