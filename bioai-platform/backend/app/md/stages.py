"""Staged MD pipeline contracts (the design's 12 modules, mapped to QC stages).

Each module is an :class:`~app.ngs.contracts.StageContract`: it declares its
inputs/outputs, runs a piece of the engine, and emits machine-auditable metrics
that the shared contract engine turns into PASS / WARN / FAIL + a decision. The
engine object lives in ``state["md_engine"]`` so every stage advances the *same*
OpenMM system.
"""

from __future__ import annotations

import logging

from app.ngs.contracts import StageContract
from app.md import qc
from app.md.engines import engine_status, gromacs_available
from app.md.structure_qc import structure_qc

logger = logging.getLogger(__name__)

MINIMIZE_STEPS = 300


def _engine(sample: dict, state: dict, *, forcefield: str | None = None, solvent: str | None = None):
    """Get (or lazily create on the preparation stage) the shared engine."""
    eng = state.get("md_engine")
    if eng is not None:
        return eng
    from app.md.engine import MdEngine

    kwargs = {}
    if sample.get("production_steps") is not None:
        kwargs["production_steps"] = sample["production_steps"]
    if sample.get("nvt_steps") is not None:
        kwargs["nvt_steps"] = sample["nvt_steps"]
    eng = MdEngine(sample["pdb_text"], sample["pdb_id"],
                   forcefield or sample.get("forcefield"),
                   solvent or sample.get("solvent"),
                   **kwargs)
    state["md_engine"] = eng
    return eng


# ── Module 1 — Input / Structure QC ─────────────────────────────────────────


def md_input_contract() -> StageContract:
    def run(sample, state):
        qc_manifest = structure_qc(sample["pdb_text"], sample["pdb_id"])
        state["md_qc"] = qc_manifest
        data = {"structure_qc": qc_manifest}
        metrics = {
            "structure_parsed": 1 if qc_manifest["parsed"] else 0,
            "protein_residues": qc_manifest["protein_residues"],
            "atom_count": qc_manifest["atom_count"],
        }
        return data, metrics

    return StageContract(
        step="md_input",
        tool="biopython",
        version="1.0",
        inputs=["pdb"],
        outputs=["structure_qc"],
        rules=[
            qc.present("structure_parsed"),
            qc.min_value("protein_residues", ok_min=1),
            qc.min_value("atom_count", ok_min=1),
        ],
        fail_blocks=True,
        run=run,
    )


# ── Module 4 — Force-field compatibility gate ───────────────────────────────


def md_ff_contract() -> StageContract:
    def run(sample, state):
        from app.tools.md_config import (
            FF_LABELS, get_verified_combos_cached, resolve_combo,
        )

        cached = get_verified_combos_cached()  # warm at startup; {} when boot verification pending
        try:
            # Fast static validation (never triggers the tens-of-seconds full
            # combinatorial probe on the hot path). Real createSystem verification
            # is enforced against the warm startup cache when available.
            ff_key, sol_key = resolve_combo(sample.get("forcefield"),
                                            sample.get("solvent"), verify=False)
            state["md_ff"] = (ff_key, sol_key)
            resolved = 1
            detail = f"{FF_LABELS.get(ff_key, ff_key)} x {sol_key.upper()}"
            if cached and sol_key not in cached.get(ff_key, ()):
                verified = 0  # warm cache says this combo did not build
                detail += f" — not in verified build set ({list(cached.get(ff_key, ()))})"
            else:
                verified = 1
        except ValueError as exc:
            resolved, verified = 0, 0
            detail = str(exc)
            ff_key, sol_key = None, None

        gmx = gromacs_available()
        data = {
            "forcefield": ff_key,
            "solvent": sol_key,
            "resolved_detail": detail,
            "boot_verification": "warm" if cached else "pending",
            "verified_combos": cached if resolved else {},
            "gromacs_available": gmx,
            "engines": engine_status(),
        }
        metrics = {
            "forcefield_resolved": resolved,
            "combo_verified": verified,
            "gromacs_available": 1 if gmx else 0,
        }
        return data, metrics

    return StageContract(
        step="md_ff",
        tool="openmm-forcefield",
        version="1.0",
        inputs=["forcefield", "solvent"],
        outputs=["resolved_ff_solvent", "engine_status"],
        rules=[
            qc.present("forcefield_resolved"),
            qc.present("combo_verified"),
            qc.warn_only_present("gromacs_available"),
        ],
        fail_blocks=True,
        run=run,
    )


# ── Module 2 — Protein preparation (+ Module 3 ligand note) ─────────────────


def md_prepare_contract() -> StageContract:
    def run(sample, state):
        ff, sol = state.get("md_ff", (sample.get("forcefield"), sample.get("solvent")))
        eng = _engine(sample, state, forcefield=ff, solvent=sol)
        data = {
            "protein": {
                "residues": eng.n_residues,
                "atoms_after_hydrogen": eng.n_particles,
                "nonstandard_removed": getattr(eng, "n_stripped", None),
                "missing_oxt_added": eng.n_oxt,
                "hydrogens_added": eng.hydrogens_added,
            },
            "ligand": {
                "present": False,
                "note": (
                    "Ligand preparation (protonation/tautomer/stereochemistry/"
                    "charges/parameters via OpenFF or Antechamber/GAFF2) is "
                    "not run in v1. The pipeline is protein-only; a protein-"
                    "ligand complex requires the ligand parameterization module."
                ),
            },
            "provenance": (
                "SWISS-MODEL/PDBFixer-class repair is performed by OpenMM Modeller "
                "(strip non-standard residues, add C-terminal OXT, add hydrogens). "
                "For missing loop segments use the Structure Preparation pipeline."
            ),
        }
        metrics = {
            "hydrogens_added": 1 if eng.hydrogens_added else 0,
            "protein_residues": eng.n_residues,
        }
        return data, metrics

    return StageContract(
        step="md_prepare",
        tool="openmm-modeller",
        version="1.0",
        inputs=["clean_pdb"],
        outputs=["prepared_topology"],
        rules=[
            qc.present("hydrogens_added"),
            qc.min_value("protein_residues", ok_min=1),
        ],
        fail_blocks=True,
        run=run,
    )


# ── Module 5 — System construction ──────────────────────────────────────────


def md_build_contract() -> StageContract:
    def run(sample, state):
        eng = _engine(sample, state)
        data = {
            "system": {
                "engine": "openmm",
                "forcefield": eng.forcefield_key,
                "implicit_solvent": eng.solvent_key.upper(),
                "cutoff_nm": 2.0,
                "particles": eng.n_particles,
                "constraints": eng.n_constraints,
                "degrees_of_freedom": eng.n_dof,
                "residues": eng.n_residues,
                "water_box": False,
                "ions": False,
                "note": (
                    "Implicit solvent (Generalized Born) — no water box or ions "
                    "are added. Explicit solvation + counterions belong to the "
                    "GROMACS path (Module 5 of the design's reference workflow)."
                ),
            },
        }
        metrics = {
            "system_built": 1,
            "particles": eng.n_particles,
        }
        return data, metrics

    return StageContract(
        step="md_build",
        tool="openmm-createSystem",
        version="1.0",
        inputs=["prepared_topology"],
        outputs=["system.gro-equivalent", "topology"],
        rules=[qc.present("system_built"), qc.min_value("particles", ok_min=1)],
        fail_blocks=True,
        run=run,
    )


# ── Module 6 — Energy minimization ──────────────────────────────────────────


def md_minimize_contract() -> StageContract:
    def run(sample, state):
        eng = _engine(sample, state)
        data, metrics = eng.minimize(max_steps=MINIMIZE_STEPS)
        return data, metrics

    return StageContract(
        step="md_minimize",
        tool="openmm-minimizeEnergy",
        version="1.0",
        inputs=["system"],
        outputs=["minimized_energy", "max_force"],
        rules=[qc.finite("energy_finite"), qc.present("energy_bounded")],
        fail_blocks=True,
        run=run,
    )


# ── Module 7 — NVT equilibration ────────────────────────────────────────────


def md_nvt_contract() -> StageContract:
    def run(sample, state):
        eng = _engine(sample, state)
        data, metrics = eng.nvt(steps=sample.get("nvt_steps"))
        return data, metrics

    return StageContract(
        step="md_nvt",
        tool="openmm-langevin-nvt",
        version="1.0",
        inputs=["minimized_system"],
        outputs=["temperature_series"],
        rules=[
            qc.finite("temperature_finite"),
            qc.max_value("temperature_cv", ok_max=0.15, warn_max=0.40),
        ],
        fail_blocks=True,
        run=run,
    )


# ── Module 8 — NPT equilibration (not-applicable in implicit solvent) ───────


def md_npt_contract() -> StageContract:
    def run(sample, state):
        eng = _engine(sample, state)
        data, metrics = eng.npt()
        return data, metrics

    return StageContract(
        step="md_npt",
        tool="openmm-barostat",
        version="1.0",
        inputs=["nvt_system"],
        outputs=["pressure_density"],
        rules=[qc.warn_only_present("pressure_coupled")],
        fail_blocks=False,
        run=run,
    )


# ── Module 9 — Production MD ────────────────────────────────────────────────


def md_production_contract() -> StageContract:
    def run(sample, state):
        eng = _engine(sample, state)
        data, metrics = eng.produce()
        return data, metrics

    return StageContract(
        step="md_production",
        tool="openmm-mdrun",
        version="1.0",
        inputs=["equilibrated_system"],
        outputs=["trajectory.xtc-equivalent", "energy.edr-equivalent"],
        rules=[
            qc.min_value("production_frames", ok_min=2),
            qc.finite("energy_finite"),
        ],
        fail_blocks=True,
        run=run,
    )


# ── Module 10 — Trajectory QC ───────────────────────────────────────────────


def md_traj_contract() -> StageContract:
    def run(sample, state):
        eng = _engine(sample, state)
        data, metrics = eng.trajectory_analysis()
        return data, metrics

    return StageContract(
        step="md_traj",
        tool="analysis",
        version="1.0",
        inputs=["trajectory"],
        outputs=["rmsd", "rmsf", "rg", "sasa"],
        rules=[
            qc.present("rmsd_computed"),
            qc.present("rmsf_computed"),
            qc.present("rg_computed"),
            qc.present("sasa_computed"),
        ],
        fail_blocks=True,
        run=run,
    )


# ── Module 11 — Convergence + final readiness ───────────────────────────────


def md_convergence_contract() -> StageContract:
    def run(sample, state):
        eng = _engine(sample, state)
        data, metrics = eng.convergence()
        return data, metrics

    return StageContract(
        step="md_convergence",
        tool="analysis-convergence",
        version="1.0",
        inputs=["trajectory_qc"],
        outputs=["convergence_table", "readiness"],
        rules=[qc.warn_only_present(m) for m in (
            "converge_energy", "converge_temperature", "converge_rmsd",
            "converge_rg", "converge_independent_replica",
        )],
        fail_blocks=False,
        run=run,
    )
