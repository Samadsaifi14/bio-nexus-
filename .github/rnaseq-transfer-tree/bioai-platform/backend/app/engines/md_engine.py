"""Molecular Dynamics Engine (BioNexus 2.0, Component 13).

Wraps the OpenMM simulation result (production time, RMSD trajectory, radius of
gyration, SASA, energy) under the independent-engine contract: parse the run
object into a canonical scientific object, validate physical invariants,
export JSON/CSV trajectories and render an RMSD trajectory figure.

Canonical input (an MD run result object):

    {
      "engine": "openmm", "forcefield": "amber14", "implicit_solvent": "IMPLICIT_GBn2",
      "temperature_k": 300, "timestep_fs": 2,
      "production_ps": 100.0, "production_steps": 50000,
      "final_energy_kj_mol": -12345.6,
      "rmsd": [{"frame": 0, "rmsd": 0.0}, ...], "rmsd_avg_angstrom": 1.4,
      "radius_of_gyration_angstrom": 11.2, "sasa_avg_angstrom2": 5320.0,
      "atom_count": 1800, "residue_count": 120, "status": "complete"
    }
"""

from __future__ import annotations

from typing import Any

from app.engines.base import BaseEngine, EngineResult, ValidationReport

MAX_TEMP_K_MIN, MAX_TEMP_K_MAX = 0.0, 1000.0
MAX_TIMESTEP_FS = 20.0


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class MDEngine(BaseEngine):
    name = "md"
    version = "1.0.0"
    tool = "OpenMM simulation + BioPython structural analysis"
    tool_version = None
    databases = ["structure (PDB atom coordinates)"]
    parameters = {
        "forcefields": ["amber14", "charmm", "gromacs"],
        "solvents": ["explicit-tip3p", "explicit-tip4pew", "implicit-gbn2"],
        "report": "RMSD / Rg / SASA / energy over trajectories",
    }
    citations = [
        "Eastman P, et al. OpenMM 8: Molecular dynamics simulation with machine learning potentials. J Phys Chem B 2024.",
        "Cock PJ, et al. Biopython. Bioinformatics 25:1422-1423, 2009.",
    ]
    benchmarks = ["MD_RMSD_AVG_NONNEGATIVE"]
    export_formats = ["json", "csv"]

    def parse(self, raw: Any) -> EngineResult:
        if not isinstance(raw, dict):
            raw = {}
        rmsd_data = raw.get("rmsd") or []
        if isinstance(rmsd_data, dict):
            rmsd_data = list(rmsd_data.values())
        return EngineResult(
            engine=self.name,
            tool=self.tool,
            database=self.databases[0],
            input_ref=f"{raw.get('forcefield', '?')} / {raw.get('implicit_solvent', 'explicit')} {raw.get('temperature_k', '?')}K",
            statistics={
                "temperature_k": _num(raw.get("temperature_k")),
                "timestep_fs": _num(raw.get("timestep_fs")),
                "production_ps": _num(raw.get("production_ps")),
                "production_steps": int(_num(raw.get("production_steps"))),
                "final_energy_kj_mol": _num(raw.get("final_energy_kj_mol")),
                "rmsd_avg_angstrom": _num(raw.get("rmsd_avg_angstrom")),
                "rmsd_max_angstrom": max((_num(r.get("rmsd")) for r in rmsd_data), default=0.0),
                "radius_of_gyration_angstrom": _num(raw.get("radius_of_gyration_angstrom")
                                                    or (rmsd_data and raw.get("radius_of_gyration"))),
                "sasa_avg_angstrom2": _num(raw.get("sasa_avg_angstrom2")),
                "atom_count": int(_num(raw.get("atom_count"))),
                "residue_count": int(_num(raw.get("residue_count"))),
            },
            evidence={
                "forcefield": raw.get("forcefield"),
                "implicit_solvent": raw.get("implicit_solvent"),
                "rmsd": rmsd_data,
                "energy": raw.get("energy") or [],
                "rmsf": raw.get("rmsf") or [],
                "status": raw.get("status"),
            },
        )

    def validate(self, result: EngineResult) -> ValidationReport:
        checks = super().validate(result).checks
        s = result.statistics
        checks.extend([
            {"name": "temperature_physical", "passed": MAX_TEMP_K_MIN < s["temperature_k"] < MAX_TEMP_K_MAX,
             "detail": f"{s['temperature_k']:.1f} K"},
            {"name": "timestep_reasonable", "passed": s["timestep_fs"] > 0 and s["timestep_fs"] <= MAX_TIMESTEP_FS,
             "detail": f"{s['timestep_fs']:.1f} fs"},
            {"name": "production_positive", "passed": s["production_ps"] > 0,
             "detail": f"{s['production_ps']:.1f} ps"},
            {"name": "rmsd_nonnegative", "passed": s["rmsd_avg_angstrom"] >= 0,
             "detail": f"avg RMSD {s['rmsd_avg_angstrom']:.2f} A"},
            {"name": "radius_of_gyration_positive", "passed": s["radius_of_gyration_angstrom"] > 0,
             "detail": f"Rg {s['radius_of_gyration_angstrom']:.2f} A"},
            {"name": "sasa_nonnegative", "passed": s["sasa_avg_angstrom2"] >= 0,
             "detail": f"SASA {s['sasa_avg_angstrom2']:.0f} A^2"},
            {"name": "structure_size_valid", "passed": s["atom_count"] > 0 and s["residue_count"] > 0,
             "detail": f"{s['atom_count']} atoms / {s['residue_count']} residues"},
        ])
        return ValidationReport(checks, self.name)

    def _export_csv(self, result: EngineResult) -> str:
        rows = ["frame,rmsd_angstrom"]
        for i, r in enumerate(result.evidence.get("rmsd") or []):
            if isinstance(r, dict):
                rows.append(f"{r.get('frame', i)},{_num(r.get('rmsd')):.3f}")
        return "\n".join(rows)

    def figure(self, result: EngineResult) -> str:
        s = result.statistics
        rmsd = [(r.get("frame", i), _num(r.get("rmsd"))) for i, r in enumerate(result.evidence.get("rmsd") or [])]
        pts = ""
        if len(rmsd) >= 2:
            frames = [f for f, _ in rmsd]
            vals = [v for _, v in rmsd]
            fmin, fmax = min(frames), max(frames)
            vmax = max(vals) * 1.05 or 1.0
            xs, ys = [], []
            for f, v in rmsd:
                x = 330 + ((f - fmin) / (fmax - fmin)) * 300
                y = 100 + (1 - v / vmax) * 240
                xs.append(x)
                ys.append(y)
            pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
            polygon = " ".join(f"{x:.1f},{y:.1f}" for x, y in [(xs[0], 340), (xs[-1], 340)])
            pts = f'<polygon points="{polygon} {pts}" fill="#3b82f6" fill-opacity="0.12"/>' \
                  f'<polyline points="{pts}" fill="none" stroke="#2563eb" stroke-width="2"/>'
        header = (
            f'<text x="30" y="30" font-size="14" font-weight="bold" fill="#111827">MD simulation summary</text>'
            f'<text x="30" y="50" font-size="10" fill="#6b7280">'
            f'{s["temperature_k"]:.0f} K · {s["production_ps"]:.1f} ps production · avg RMSD {s["rmsd_avg_angstrom"]:.2f} A</text>'
        )
        stats = (
            f'<text x="30" y="94" font-size="10" fill="#374151">Rg {s["radius_of_gyration_angstrom"]:.2f} A</text>'
            f'<text x="30" y="112" font-size="10" fill="#374151">SASA {s["sasa_avg_angstrom2"]:.0f} A^2</text>'
            f'<text x="30" y="130" font-size="10" fill="#374151">E_final {s["final_energy_kj_mol"]:.0f} kJ/mol</text>'
            f'<text x="30" y="148" font-size="10" fill="#374151">{s["atom_count"]} atoms · {s["residue_count"]} residues</text>'
        )
        footer = f'<text x="660" y="380" font-size="9" fill="#6b7280">Generated by BioNexus MD Engine v{self.version}</text>'
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="680" height="400" '
            'viewBox="0 0 680 400" font-family="Helvetica, Arial, sans-serif">'
            '<rect x="0" y="0" width="680" height="400" fill="#ffffff" rx="8"/>'
            f'{header}{stats}<text x="330" y="88" font-size="10" fill="#6b7280">RMSD vs frame</text>'
            f'{pts}'
            f'<line x1="330" y1="340" x2="630" y2="340" stroke="#e5e7eb"/>'
            f'{footer}</svg>'
        )


md_engine = MDEngine()