"""Staged Molecular Dynamics pipeline router (MD v2).

Runs the auditable short implicit-solvent OpenMM DAG and exposes the exact
backend-emitted stage data to the frontend.  Plot descriptors reference retained
stage arrays directly; no plotting layer fabricates or recalculates scientific
values.  Missing arrays simply mean that plot is unavailable.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.md.advanced_analysis import analyze_trajectory
from app.md.engines import engine_status
from app.md.orchestrator import STAGE_INTRO, build_md_pipeline
from app.science.result import build_scientific_result

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/md/v2", tags=["md-v2"])
SYNC_PRODUCTION_MAX_PS = 20.0


class AnalyzeRequest(BaseModel):
    pdb_id: str = Field(..., min_length=1, max_length=32, description="PDB ID or structure label")
    forcefield: Optional[str] = Field(default=None, pattern=r"^[a-z0-9_-]+$", description="Force field key from GET /api/md/forcefields")
    solvent: Optional[str] = Field(default=None, pattern=r"^(obc1|obc2|gbn2)$", description="Implicit solvent model")
    production_ps: Optional[float] = Field(default=None, ge=1, le=5000, description="Desired production length in ps")
    nvt_ps: Optional[float] = Field(default=None, ge=5, le=5000)
    pdb_text: Optional[str] = Field(default=None, description="Explicit PDB text for tests/offline use")


class TrajectoryAnalysisRequest(BaseModel):
    coordinates: list[list[list[float]]] = Field(..., description="Cartesian trajectory [frames][atoms][xyz], in angstrom")
    masses: list[float] | None = None
    atom_radii: list[float] | None = Field(default=None, description="van der Waals radii in angstrom; required for SASA")
    hydrogen_bond_triples: list[list[int]] | None = Field(default=None, description="[donor, hydrogen, acceptor] atom indices")
    secondary_structure_timeline: list[Any] | None = Field(default=None, description="Topology-aware DSSP/secondary-structure assignments if already computed")
    contact_cutoff: float = Field(default=8.0, gt=0, le=30)
    temperature_k: float = Field(default=300.0, gt=0, le=1000)
    pca_components: int = Field(default=3, ge=1, le=20)
    free_energy_bins: int = Field(default=30, ge=5, le=100)


def _stage(report: dict[str, Any], step: str) -> dict[str, Any] | None:
    for item in report.get("stages", []) or []:
        if item.get("step") == step:
            return item
    return None


def _data(report: dict[str, Any], step: str) -> dict[str, Any]:
    found = _stage(report, step)
    value = found.get("data") if found else None
    return value if isinstance(value, dict) else {}


def _series_plot(
    *,
    plot_id: str,
    title: str,
    x_label: str,
    y_label: str,
    data: Any,
    x_key: str,
    y_key: str,
    source_stage: str,
) -> dict[str, Any] | None:
    """Describe one plot without changing any scientific values."""
    if not isinstance(data, list) or not data:
        return None
    retained = [row for row in data if isinstance(row, dict) and x_key in row and y_key in row and row.get(y_key) is not None]
    if not retained:
        return None
    return {
        "id": plot_id,
        "title": title,
        "kind": "line",
        "x_label": x_label,
        "y_label": y_label,
        "x_key": x_key,
        "y_key": y_key,
        "source_stage": source_stage,
        "data": retained,
    }


def _plots_from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose only retained MD arrays.  No data means no plot."""
    nvt = _data(report, "md_nvt")
    production = _data(report, "md_production")
    traj = _data(report, "md_traj")

    candidates = [
        _series_plot(
            plot_id="temperature-vs-step",
            title="Temperature vs step",
            x_label="Step",
            y_label="Temperature (K)",
            data=nvt.get("temperature"),
            x_key="step",
            y_key="temperature_k",
            source_stage="md_nvt",
        ),
        _series_plot(
            plot_id="potential-energy-vs-step",
            title="Potential energy vs step",
            x_label="Step",
            y_label="Potential energy (kJ/mol)",
            data=production.get("potential_energy") or production.get("energy"),
            x_key="step",
            y_key="potential_energy_kj_mol",
            source_stage="md_production",
        ),
        _series_plot(
            plot_id="rmsd-vs-frame",
            title="RMSD vs frame",
            x_label="Frame",
            y_label="RMSD (Å)",
            data=traj.get("rmsd"),
            x_key="frame",
            y_key="rmsd",
            source_stage="md_traj",
        ),
        _series_plot(
            plot_id="rmsf-vs-residue",
            title="RMSF vs residue",
            x_label="Residue",
            y_label="RMSF (Å)",
            data=traj.get("rmsf"),
            x_key="residue",
            y_key="rmsf_angstrom",
            source_stage="md_traj",
        ),
        _series_plot(
            plot_id="radius-of-gyration-vs-step",
            title="Radius of gyration vs step",
            x_label="Step",
            y_label="Radius of gyration (Å)",
            data=production.get("radius_of_gyration") or production.get("rg"),
            x_key="step",
            y_key="rg_angstrom",
            source_stage="md_production",
        ),
        _series_plot(
            plot_id="sasa-vs-step",
            title="SASA vs step",
            x_label="Step",
            y_label="SASA (Å²)",
            data=traj.get("sasa"),
            x_key="step",
            y_key="sasa_angstrom2",
            source_stage="md_traj",
        ),
    ]
    return [plot for plot in candidates if plot is not None]


def _stage_errors(report: dict[str, Any]) -> list[dict[str, str]]:
    """Return explicit engine exceptions and blocking QC failures.

    A stage can stop scientifically without raising a Python exception.  Those
    QC failures must still be visible to the researcher; otherwise a failed
    run appears to contain no result and no reason.
    """
    errors: list[dict[str, str]] = []
    for item in report.get("stages", []) or []:
        if not isinstance(item, dict):
            continue
        stage_name = str(item.get("step") or "unknown")
        data = item.get("data")
        qc = item.get("qc")

        if isinstance(data, dict) and data.get("error"):
            errors.append({"stage": stage_name, "error": str(data["error"])})
            continue

        if isinstance(qc, dict) and str(qc.get("status") or "").upper() == "FAIL":
            reasons: list[str] = []
            for metric in qc.get("metrics", []) or []:
                if not isinstance(metric, dict) or str(metric.get("status") or "").upper() != "FAIL":
                    continue
                name = str(metric.get("name") or "QC metric")
                detail = metric.get("detail") or metric.get("expected")
                reasons.append(f"{name}: {detail}" if detail else name)
            errors.append({
                "stage": stage_name,
                "error": "; ".join(reasons) if reasons else "Blocking QC failure",
            })
    return errors


@router.get("/stages")
def list_stages():
    pipe = build_md_pipeline()
    return {
        "pipeline": pipe.name,
        "version": pipe.version,
        "stages": [
            {"step": c.step, "tool": c.tool, "inputs": c.inputs, "outputs": c.outputs,
             "fail_blocks": c.fail_blocks, "expectation": STAGE_INTRO.get(c.step, "")}
            for c in pipe.stages
        ],
    }


@router.get("/engine")
def get_engine_status():
    return engine_status()


@router.post("/trajectory/analyze")
def advanced_trajectory_analysis(payload: TrajectoryAnalysisRequest):
    """Generate RMSD/RMSF/Rg/SASA/H-bonds/contact-map/DCCM/PCA/FEL outputs.

    SASA, hydrogen bonds and secondary-structure output are marked unavailable
    unless their required radii/topology assignments are supplied. Coordinates
    are Kabsch-aligned before fluctuation/correlation analyses.
    """
    try:
        return analyze_trajectory(
            payload.coordinates,
            masses=payload.masses,
            atom_radii=payload.atom_radii,
            hydrogen_bond_triples=payload.hydrogen_bond_triples,
            secondary_structure_timeline=payload.secondary_structure_timeline,
            contact_cutoff=payload.contact_cutoff,
            temperature_k=payload.temperature_k,
            pca_components=payload.pca_components,
            free_energy_bins=payload.free_energy_bins,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Advanced MD trajectory analysis failed")
        raise HTTPException(status_code=500, detail=f"trajectory analysis failed: {type(exc).__name__}: {exc}") from exc


@router.post("/analyze")
async def analyze(payload: AnalyzeRequest):
    if payload.pdb_text:
        pdb_text = payload.pdb_text
        pdb_id = payload.pdb_id
    else:
        try:
            from app.tools.structure_prep import fetch_pdb_text
            pdb_text = await fetch_pdb_text(payload.pdb_id)
            pdb_id = payload.pdb_id.upper()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"failed to fetch PDB {payload.pdb_id}: {exc}")

    if not pdb_text or "ATOM" not in pdb_text:
        raise HTTPException(status_code=400, detail="structure contains no ATOM records")

    requested_production_ps = payload.production_ps
    effective_production_ps = min(float(requested_production_ps), SYNC_PRODUCTION_MAX_PS) if requested_production_ps is not None else None
    production_was_capped = requested_production_ps is not None and effective_production_ps is not None and float(requested_production_ps) > effective_production_ps

    sample: dict = {"pdb_id": pdb_id, "pdb_text": pdb_text, "forcefield": payload.forcefield, "solvent": payload.solvent}
    if effective_production_ps is not None:
        sample["production_steps"] = int(effective_production_ps * 1000 / 2.0)
    if payload.nvt_ps:
        sample["nvt_steps"] = int(payload.nvt_ps * 1000 / 2.0)

    pipe = build_md_pipeline()
    try:
        report = await asyncio.to_thread(pipe.run, sample)
    except Exception as exc:
        logger.exception("MD v2 pipeline failed for %s", pdb_id)
        raise HTTPException(status_code=503, detail=f"MD engine failed before producing a scientific result: {type(exc).__name__}: {exc}") from exc

    warnings = report.setdefault("warnings", [])
    if production_was_capped:
        warnings.append(
            f"Requested production length {requested_production_ps:g} ps was capped to {effective_production_ps:g} ps for synchronous hosted execution. Use the durable MD workflow for longer trajectories."
        )

    requested = {
        "pdb_id": pdb_id,
        "forcefield": payload.forcefield or "default (amber14)",
        "solvent": payload.solvent or "default (obc2)",
        "production_ps": requested_production_ps,
        "effective_production_ps": effective_production_ps,
        "production_capped": production_was_capped,
        "synchronous_limit_ps": SYNC_PRODUCTION_MAX_PS,
        "source": "provided-pdb-text" if payload.pdb_text else "rcsb",
    }

    pipeline_status = str(report.get("pipeline_status") or "FAIL").upper()
    scientific_status = "VALID" if pipeline_status == "PASS" else "DEGRADED" if pipeline_status == "WARN" else "FAILED"
    errors = _stage_errors(report)
    plots = _plots_from_report(report)
    engine = engine_status()
    openmm = (engine.get("engines") or {}).get("openmm") or {}
    engine_version = str(openmm.get("version") or "unavailable")
    production = _data(report, "md_production")
    trajectory = _data(report, "md_traj")
    convergence = _data(report, "md_convergence")

    validation = {
        "scope": "Short implicit-solvent OpenMM MD; not an explicit-solvent production MD protocol",
        "pipeline_status": pipeline_status,
        "pipeline_decision": report.get("pipeline_decision"),
        "stopped_at": report.get("stopped_at"),
        "stage_errors": errors,
        "real_trajectory_emitted": bool(production.get("n_frames")),
        "trajectory_qc_emitted": bool(trajectory.get("rmsd")),
        "convergence_assessment_emitted": bool(convergence.get("convergence")),
        "independent_scientific_validation": False,
    }

    scientific = build_scientific_result(
        status=scientific_status,
        method="Short implicit-solvent OpenMM MD",
        engine="OpenMM",
        engine_version=engine_version,
        input_payload={"pdb_text": pdb_text, "requested": requested},
        parameters={
            "forcefield": requested["forcefield"],
            "solvent": requested["solvent"],
            "requested_production_ps": requested_production_ps,
            "effective_production_ps": effective_production_ps,
            "nvt_ps": payload.nvt_ps,
        },
        results={"requested": requested, "pipeline": report},
        plots=plots,
        artifacts=[],
        evidence_class="Deterministic computation",
        validation=validation,
        citations=[{"label": "OpenMM", "url": "https://openmm.org/"}],
    )

    # Compatibility keys remain top-level while clients migrate to ScientificResult.
    scientific["requested"] = requested
    scientific["pipeline"] = report
    return scientific
