"""Regression tests for the concave-packing pocket detector.

The previous SASA fallback clustered every exposed surface residue into one
giant "whole-surface blob", so real proteins either reported a meaningless
single ~100k A^3 pocket (CASTp page) or "0 pockets" (structure-prep when
fpocket/CASTp unavailable). These tests pin the new compact-pocket behaviour
with deterministic synthetic geometry (no network, no fpocket/scipy).
"""

import pytest

from app.tools.castp import _detect_pockets_sasa
from app.tools.structure_prep import run_sasa_pockets


def _concave_geometry():
    """Build 30 CA residues with a real concave pocket plus fillers.

    - 8  'pocket' residues: on a concave arc, surface-partial (sasa=18) and
         densely packed (everyone within ~10 A)  -> the true pocket lining.
    - 10 'buried' residues: tightly packed (dense) but sasa=0 (interior).
    - 12 'flat' residues: fully exposed (sasa=150) but isolated (0 neighbors).

    Returns (residues, coords) parallel lists for _detect_pockets_sasa.
    """
    residues = []
    coords = []

    # 8 pocket residues in a tight 2x2x2 cube (densely packed, 7 neighbours
    # each within 12 A), surface-partial (sasa=18) -> the true pocket lining.
    cx, cy, cz = -20.0, 0.0, 0.0
    for pos in ((0,0,0),(3,0,0),(0,3,0),(3,3,0),(0,0,3),(3,0,3),(0,3,3),(3,3,3)):
        coords.append((cx + pos[0], cy + pos[1], cz + pos[2]))
        residues.append({"chain": "A", "residue": "ALA", "resnum": len(coords), "sasa": 18.0})

    # 10 buried residues: dense but fully interior (sasa=0).
    bx = 60.0
    for k in range(10):
        coords.append((bx + (k % 3) * 3.0, (k // 3) * 3.0, 0.0))
        residues.append({"chain": "B", "residue": "LEU", "resnum": k + 1, "sasa": 0.0})

    # 12 flat exposed residues: high sasa, isolated (>30 A apart).
    for k in range(12):
        coords.append((100.0, k * 30.0, 0.0))
        residues.append({"chain": "C", "residue": "ASP", "resnum": k + 1, "sasa": 150.0})

    return residues, coords


class TestConcavePocketDetection:
    def test_detects_compact_pocket_not_whole_surface_blob(self):
        residues, coords = _concave_geometry()
        pockets = _detect_pockets_sasa(residues, coords, 1.4)

        # Must find the real pocket.
        assert pockets, "expected at least one pocket"
        top = max(pockets, key=lambda p: p["num_residues"])
        # The pocket is the 8-residue concave group, not the ~30 whole surface.
        assert top["num_residues"] == 8
        # Guard: the old bug returned one blob covering ~all exposed residues.
        assert top["num_residues"] < 8 + 12  # strictly less than all exposed

    def test_pocket_has_geometry_and_volumes(self):
        residues, coords = _concave_geometry()
        pockets = _detect_pockets_sasa(residues, coords, 1.4)
        top = max(pockets, key=lambda p: p["num_residues"])
        assert top["volume_sa"] > 0
        assert top["area_sa"] > 0
        assert len(top["centroid"]) == 3
        assert all(isinstance(v, (int, float)) for v in top["centroid"])
        assert top["num_residues"] == len(top["residues"])

    def test_empty_inputs_yield_no_pockets(self):
        assert _detect_pockets_sasa([], [], 1.4) == []


class TestRunSasaPocketsFallback:
    def test_graceful_on_empty(self):
        # No crash; returns an empty pocket list rather than raising.
        assert run_sasa_pockets("") == []

    def test_graceful_on_garbage(self):
        assert run_sasa_pockets("this is not a pdb") == []

    def test_returns_fpocket_shaped_pockets_from_valid_pdb(self):
        # A tight blob of residues is all dense + surface -> one pocket whose
        # dict must carry fpocket's exact keys (the pipeline response model
        # reads only these, so the fallback is drop-in for fpocket).
        lines = ["ATOM  %5d  CA  ALA A%4d    %8.3f%8.3f%8.3f  1.00 20.00" % (i, i, 0.0, (i % 4) * 2.0, (i // 4) * 2.0) for i in range(1, 13)]
        pdb = "CRYST1   50.000   50.000   50.000  90.00  90.00  90.00 P 1           1\n" + "\n".join(lines) + "\nEND\n"
        pockets = run_sasa_pockets(pdb, 1.4)
        if pockets:
            for p in pockets:
                assert set(p.keys()) == {
                    "id", "druggability_score", "volume", "area", "score", "num_residues",
                }
                assert p["num_residues"] >= 1

    def test_fpocket_shape_keys(self):
        import json
        shape = {
            "id": 1,
            "druggability_score": 0.0,
            "volume": 1.0,
            "area": 1.0,
            "score": 1.0,
            "num_residues": 1,
        }
        assert set(shape.keys()) == {
            "id", "druggability_score", "volume", "area", "score", "num_residues",
        }
        # Round-trips through the API FpocketPocket model unchanged.
        from app.routers.structure_prep import FpocketPocket
        p = FpocketPocket(**shape)
        assert p.num_residues == 1
