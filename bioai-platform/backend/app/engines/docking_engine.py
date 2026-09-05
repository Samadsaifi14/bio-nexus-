"""Docking Engine (BioNexus 2.0, Component 12).

Wraps the AutoDock Vina docking result (poses, affinities, interaction map)
under the independent-engine contract: parse the per-run result object into a
canonical scientific object, validate the physics invariants (finite affinities
in a sane range, non-negative RMSD, consistent pose count), export a per-pose
table (JSON/CSV) and render an affinity + interaction figure.

Canonical input (a docking result object, e.g. from /api/docking):

    {
      "pdb_id": "...", "smiles": "...",
      "num_poses": 9,
      "poses": [{"affinity": -9.5, "rmsd_lb": 0.0, "rmsd_ub": 0.5, ...}],
      "interactions": {"h_bonds": 2, "hydrophobic": 3, "pi_stacking": 1, "salt_bridges": 0},
      "box_center": {"x": .., "y": .., "z": ..}, "box_size": {"x": .., "y": .., "z": ..},
      "vina_version": "1.2.5", "vina_seed": 42
    }
"""

from __future__ import annotations

from typing import Any

from app.engines.base import BaseEngine, EngineResult, ValidationReport
from app.figure.engine import bar_chart_panel, esc

#: Sanity window for Vina affinities in kcal/mol (wider than the typical
#: ligand window so genuinely broken results still fail loudly).
AFFINITY_MIN, AFFINITY_MAX = -60.0, 30.0


def _fnum(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class DockingEngine(BaseEngine):
    name = "docking"
    version = "1.0.0"
    tool = "AutoDock Vina (with interaction profiling)"
    tool_version = None
    databases = ["PDB/receptor (from structure stage)"]
    parameters = {
        "search": "AutoDock Vina (exhaustiveness/num_modes)",
        "rescoring": "optional Gnina CNN rescoring (graceful fallback)",
        "interactions": "H-bonds, hydrophobic, pi stacking, salt bridges from PDB ligand pose",
        "affinity_window_kcal_mol": [AFFINITY_MIN, AFFINITY_MAX],
    }
    citations = [
        "Trott O, Olson AJ. AutoDock Vina: improving the speed and accuracy of docking. J Comput Chem 31:455-461, 2010.",
        "Lu J, et al. Universal and efficient ligand binding pose prediction. Nat Protoc (Gnina rescoring) 2024.",
    ]
    benchmarks = ["DOCKING_P53_APRIL_VINA_AFFINITY_BOUNDED"]
    export_formats = ["json", "csv"]

    def parse(self, raw: Any) -> EngineResult:
        if not isinstance(raw, dict):
            raw = {}
        poses = raw.get("poses") or []
        if isinstance(poses, dict):
            poses = list(poses.values())
        affinities = [_fnum(p.get("affinity")) for p in poses if isinstance(p, dict)]
        interactions = raw.get("interactions") or {}
        best = min(affinities) if affinities else None
        stats: dict[str, Any] = {
            "num_poses": int(raw.get("num_poses") or len(poses)),
            "pose_count": len(poses),
            "best_affinity": best if best is not None else float("nan"),
            "worst_affinity": max(affinities) if affinities else float("nan"),
            "mean_affinity": (sum(affinities) / len(affinities)) if affinities else float("nan"),
            "h_bonds": int(interactions.get("h_bonds", 0) or interactions.get("hydrogen_bonds", 0) or 0),
            "hydrophobic": int(interactions.get("hydrophobic", 0) or 0),
            "pi_stacking": int(interactions.get("pi_stacking", 0) or 0),
            "salt_bridges": int(interactions.get("salt_bridges", 0) or 0),
        }
        return EngineResult(
            engine=self.name,
            tool=self.tool,
            database=self.databases[0],
            input_ref=f"{raw.get('pdb_id')} x {raw.get('smiles', '?')[:50]}",
            statistics=stats,
            evidence={
                "vina_version": raw.get("vina_version"),
                "vina_seed": raw.get("vina_seed"),
                "box_center": raw.get("box_center"),
                "box_size": raw.get("box_size"),
                "cnn_rescoring": raw.get("cnn_rescoring"),
                "poses": poses,
            },
            exports=["json", "csv"],
        )

    def validate(self, result: EngineResult) -> ValidationReport:
        checks = super().validate(result).checks
        s = result.statistics
        poses: list = result.evidence.get("poses") or []

        affinity_ok = True
        best = s["best_affinity"]
        if s["pose_count"]:
            affinity_ok = all(AFFINITY_MIN <= _fnum(p.get("affinity")) <= AFFINITY_MAX for p in poses)

        rmsd_ok = all(
            (_fnum(p.get("rmsd_lb"), 0.0) >= 0) and (_fnum(p.get("rmsd_ub"), 0.0) >= 0)
            for p in poses if isinstance(p, dict)
        )
        box = result.evidence.get("box_size") or {}
        box_ok = all(_fnum(box.get(k)) > 0 for k in ("x", "y", "z")) if box else True

        checks.extend([
            {"name": "poses_present", "passed": s["pose_count"] >= 1, "detail": f"{s['pose_count']} poses"},
            {"name": "num_poses_consistent", "passed": s["num_poses"] == s["pose_count"],
             "detail": f"declared {s['num_poses']} vs parsed {s['pose_count']}"},
            {"name": "affinities_finite_in_window", "passed": affinity_ok and s["pose_count"] > 0,
             "detail": f"best={best:.2f} kcal/mol" if isinstance(best, float) and not (best != best) else "n/a"},
            {"name": "rmsd_nonnegative", "passed": rmsd_ok, "detail": "all RMSD values >= 0"},
            {"name": "interactions_nonnegative", "passed": all(v >= 0 for v in
             (s["h_bonds"], s["hydrophobic"], s["pi_stacking"], s["salt_bridges"])), "detail": "interaction counts"},
            {"name": "grid_box_valid", "passed": box_ok, "detail": "positive box sizes"},
        ])
        return ValidationReport(checks, self.name)

    def _export_csv(self, result: EngineResult) -> str:
        poses: list = result.evidence.get("poses") or []
        rows = ["pose,affinity,rmsd_lb,rmsd_ub"]
        for i, p in enumerate(poses, 1):
            if isinstance(p, dict):
                rows.append(f"{i},{_fnum(p.get('affinity')):.3f},{_fnum(p.get('rmsd_lb'), 0.0):.3f},{_fnum(p.get('rmsd_ub'), 0.0):.3f}")
        return "\n".join(rows)

    def figure(self, result: EngineResult) -> str:
        s = result.statistics
        aff_rows = [("Best", abs(s["best_affinity"]) if s["best_affinity"] == s["best_affinity"] else 0.0)]
        inter_rows = [
            ("H-bonds", float(s["h_bonds"])),
            ("Hydrophobic", float(s["hydrophobic"])),
            ("Pi stacking", float(s["pi_stacking"])),
            ("Salt bridges", float(s["salt_bridges"])),
        ]
        body = bar_chart_panel(aff_rows, x=30, y=70, w=180, h=120, value_label="kcal/mol")
        body += bar_chart_panel(inter_rows, x=240, y=70, w=280, h=220, value_label="count")
        header = (
            f'<text x="30" y="32" font-size="14" font-weight="bold" fill="#111827">Docking summary</text>'
            f'<text x="30" y="52" font-size="10" fill="#6b7280">best affinity {s["best_affinity"]:.2f} kcal/mol · '
            f'{s["pose_count"]} poses · mean {s["mean_affinity"]:.2f}</text>'
        )
        footer = f'<text x="30" y="340" font-size="9" fill="#6b7280">Generated by BioNexus Docking Engine v{self.version}</text>'
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="560" height="360" '
            'viewBox="0 0 560 360" font-family="Helvetica, Arial, sans-serif">'
            '<rect x="0" y="0" width="560" height="360" fill="#ffffff" rx="8"/>'
            f"{header}{body}{footer}</svg>"
        )


docking_engine = DockingEngine()