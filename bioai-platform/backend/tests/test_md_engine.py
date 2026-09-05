"""MD Engine (Component 13) unit tests — no DB, no OpenMM."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines import ENGINES, md_engine

MD_OK = {
    "engine": "openmm",
    "forcefield": "amber14",
    "implicit_solvent": "IMPLICIT_GBn2",
    "temperature_k": 300,
    "timestep_fs": 2,
    "production_ps": 100.0,
    "production_steps": 50000,
    "final_energy_kj_mol": -12345.6,
    "rmsd": [{"frame": 0, "rmsd": 0.0}, {"frame": 100, "rmsd": 1.2}, {"frame": 200, "rmsd": 1.6}],
    "rmsd_avg_angstrom": 1.4,
    "radius_of_gyration_angstrom": 11.2,
    "sasa_avg_angstrom2": 5320.0,
    "atom_count": 1800,
    "residue_count": 120,
    "status": "complete",
}


def test_registered_in_registry():
    assert "md" in ENGINES


def test_parse_statistics():
    s = md_engine.parse(MD_OK).statistics
    assert s["production_ps"] == 100.0
    assert abs(s["rmsd_avg_angstrom"] - 1.4) < 1e-6
    assert s["residue_count"] == 120
    assert abs(s["rmsd_max_angstrom"] - 1.6) < 1e-6


def test_validate_passes_good_simulation():
    report = md_engine.validate(md_engine.parse(MD_OK))
    assert report.valid, [c for c in report.checks if not c["passed"]]


def test_validate_rejects_negative_rmsd():
    raw = dict(MD_OK)
    raw["rmsd_avg_angstrom"] = -2.0
    report = md_engine.validate(md_engine.parse(raw))
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "rmsd_nonnegative" in names


def test_validate_rejects_unphysical_temperature():
    raw = dict(MD_OK)
    raw["temperature_k"] = 5000
    report = md_engine.validate(md_engine.parse(raw))
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "temperature_physical" in names


def test_validate_rejects_absent_production():
    raw = dict(MD_OK)
    raw["production_ps"] = 0
    report = md_engine.validate(md_engine.parse(raw))
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "production_positive" in names


def test_export_csv_rmsd_trace():
    csv = md_engine.export(md_engine.parse(MD_OK), "csv")
    assert csv.startswith("frame,rmsd_angstrom")
    assert len(csv.splitlines()) == 4


def test_figure_svg_has_trajectory():
    svg = md_engine.figure(md_engine.parse(MD_OK))
    assert svg.count("<svg") == svg.count("</svg>")
    assert "MD simulation summary" in svg
    assert "<polyline" in svg


def test_validate_empty_degrades():
    assert not md_engine.validate(md_engine.parse(None)).valid