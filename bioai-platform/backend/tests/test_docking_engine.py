"""Docking Engine (Component 12) unit tests — no DB, no binary deps."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines import ENGINES, docking_engine

DOCK_OK = {
    "pdb_id": "1ai8",
    "smiles": "COc1ccccc1",
    "num_poses": 3,
    "poses": [
        {"affinity": -9.4, "rmsd_lb": 0.0, "rmsd_ub": 0.4},
        {"affinity": -8.7, "rmsd_lb": 1.2, "rmsd_ub": 2.1},
        {"affinity": -7.9, "rmsd_lb": 2.4, "rmsd_ub": 3.8},
    ],
    "interactions": {"h_bonds": 2, "hydrophobic": 3, "pi_stacking": 1, "salt_bridges": 0},
    "box_center": {"x": 1, "y": 2, "z": 3},
    "box_size": {"x": 24, "y": 24, "z": 24},
    "vina_version": "1.2.5",
    "vina_seed": 42,
}


def test_registered_in_registry():
    assert "docking" in ENGINES


def test_parse_statistics_affinities():
    result = docking_engine.parse(DOCK_OK)
    s = result.statistics
    assert s["num_poses"] == 3
    assert abs(s["best_affinity"] - (-9.4)) < 1e-6
    assert abs(s["mean_affinity"] - (-8.6666667)) < 1e-4
    assert s["h_bonds"] == 2


def test_validate_passes_good_docking():
    report = docking_engine.validate(docking_engine.parse(DOCK_OK))
    assert report.valid, [c for c in report.checks if not c["passed"]]


def test_validate_fails_no_poses():
    raw = dict(DOCK_OK)
    raw["poses"] = []
    raw["num_poses"] = 0
    report = docking_engine.validate(docking_engine.parse(raw))
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "poses_present" in names


def test_validate_fails_affinity_out_of_window():
    raw = dict(DOCK_OK)
    raw["poses"] = [{"affinity": 500.0, "rmsd_lb": 0, "rmsd_ub": 0}]
    report = docking_engine.validate(docking_engine.parse(raw))
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "affinities_finite_in_window" in names


def test_validate_fails_negative_rmsd():
    raw = dict(DOCK_OK)
    raw["poses"] = [{"affinity": -8.0, "rmsd_lb": -1.0, "rmsd_ub": 0.5}]
    report = docking_engine.validate(docking_engine.parse(raw))
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "rmsd_nonnegative" in names


def test_validate_fails_bad_box():
    raw = dict(DOCK_OK)
    raw["box_size"] = {"x": -5, "y": 0, "z": 24}
    report = docking_engine.validate(docking_engine.parse(raw))
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "grid_box_valid" in names


def test_export_csv_pose_table():
    csv = docking_engine.export(docking_engine.parse(DOCK_OK), "csv")
    assert csv.startswith("pose,affinity,rmsd_lb,rmsd_ub")
    assert len(csv.splitlines()) == 4  # header + 3 poses


def test_figure_svg_valid():
    svg = docking_engine.figure(docking_engine.parse(DOCK_OK))
    assert svg.count("<svg") == svg.count("</svg>")
    assert "Docking summary" in svg


def test_validate_empty_degrades():
    assert not docking_engine.validate(docking_engine.parse(None)).valid