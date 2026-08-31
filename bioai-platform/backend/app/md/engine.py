"""Stateful OpenMM MD engine with per-stage operations.

This is the physics core of the staged MD pipeline (the design's "GROMACS +
OpenMM" engine seam, GROMACS path gated). It holds one OpenMM :class:`Simulation`
across the whole DAG so each stage advances the *same* system — minimization,
NVT, production — and later stages analyse the resulting trajectory. Each public
method returns ``(data, metric_values)`` so the QC contract engine can wrap it in
a machine-auditable StageResult.

The force-field/solvent menu and construction path re-use the already-verified
setup in :mod:`app.tools.md_config` (every combo is probe-verified at import). The
heavy numerical helpers (Kabsch RMSD, RMSF, Rg, SASA, temperature-from-KE) are
imported from :mod:`app.tools.md_sim` so there is exactly one implementation.

Implicit solvent only (v1): there is no periodic box, so NPT (pressure coupling)
is reported not-applicable — the GROMACS explicit-solvent path is where real NPT
belongs.
"""

from __future__ import annotations

import io
import logging
import math
import os
import time

import numpy as np

from app.tools.md_config import DEFAULT_FORCEFIELD, DEFAULT_SOLVENT, FF_LABELS, resolve_combo
from app.tools.md_sim import (
    _VDW_RADII,
    _add_missing_terminal_oxt,
    _compute_rmsf,
    _kabsch_rmsd,
    _positions_to_np,
    _radius_of_gyration,
    _sasa_shrake_ruger,
    _strip_non_standard_residues,
    _temperature_from_ke,
    _to_native,
)

logger = logging.getLogger(__name__)

# Tangible simulation constants (kept small so the staged DAG completes inside
# the free-tier job window while still producing a real micro-trajectory, AND
# inside typical reverse-proxy upstream timeouts — several minutes blocks the
# synchronous endpoint and surfaces as a gateway 502).
TARGET_KELVIN = 300.0
TIMESTEP_FS = 2.0           # Langevin middle, 2 fs
NVT_STEPS = 300             # equilibration
PRODUCTION_TARGET_PS = 80.0
PRODUCTION_MAX_PS = 300.0
PRODUCTION_MIN_PS = 1.0
_PRODUCTION_BUDGET_SECONDS = 18.0
_EST_STEPS_PER_SEC = 1_400_000.0

# Non-bonded setup (matches md_config verification probe).
CUTOFF_NM = 2.0


class MdEngine:
    """One OpenMM system, advanced stage-by-stage for the MD pipeline."""

    def __init__(
        self,
        pdb_text: str,
        pdb_id: str,
        forcefield: str | None = None,
        solvent: str | None = None,
        *,
        production_steps: int | None = None,
        nvt_steps: int = NVT_STEPS,
        temperature_k: float = TARGET_KELVIN,
    ):
        self.pdb_text = pdb_text
        self.pdb_id = pdb_id.upper().strip()
        self.forcefield_key, self.solvent_key = resolve_combo(
            forcefield, solvent, verify=False)
        self.forcefield_label = FF_LABELS.get(self.forcefield_key, self.forcefield_key)
        self.temperature_k = temperature_k
        self._production_steps = production_steps
        self._nvt_steps = nvt_steps

        self.simulation = None
        self.modeller = None
        self.forcefield = None
        self.receptor_prefix = "R"

        # Prepared-structure metadata
        self.n_std = 0
        self.stripped: list[str] = []       # non-standard residues removed
        self.n_oxt = 0
        self.hydrogens_added = False
        self.n_particles = 0
        self.n_constraints = 0
        self.n_dof = 0

        # Reference (minimized) CA coordinates + heavy radii for metrics.
        self._ref_coords: np.ndarray | None = None
        self._ca_indices: list[int] = []
        self._heavy_indices: list[int] = []
        self._heavy_radii: np.ndarray | None = None
        self._atom_to_residue: dict[int, str] = {}

        # Trajectory data (production).
        self.frames: list[np.ndarray] = []
        self.frame_steps: list[int] = []
        self.production_energy: list[float] = []
        self.temperature_series: list[dict] = []   # {"step":, "temperature_k":, "kinetic_kj_mol":}
        self.rg_series: list[dict] = []            # {"step":, "rg_angstrom":}

        # Equilibration (NVT) temperature series.
        self.eq_temperature: list[dict] = []

        self._init_openmm()

    # ------------------------------------------------------------------
    # Structure preparation + system construction
    # ------------------------------------------------------------------

    def _init_openmm(self) -> None:
        from openmm.app import PDBFile, ForceField, Modeller, CutoffNonPeriodic
        from openmm import unit

        from app.tools.md_config import FF_XML, SOLVENT_XML

        pdb = PDBFile(io.StringIO(self.pdb_text))
        self.forcefield = ForceField(FF_XML[self.forcefield_key], SOLVENT_XML[self.solvent_key])
        self.modeller = Modeller(pdb.topology, pdb.positions)

        self.n_stripped = _strip_non_standard_residues(self.modeller)
        self.n_oxt = _add_missing_terminal_oxt(self.modeller)
        self.modeller.addHydrogens(self.forcefield)
        self.hydrogens_added = True

        self.n_residues = len(list(self.modeller.topology.residues()))
        if self.n_residues == 0:
            raise RuntimeError(f"PDB {self.pdb_id} contains no protein residues to simulate")

        self._system = self.forcefield.createSystem(
            self.modeller.topology,
            nonbondedMethod=CutoffNonPeriodic,
            nonbondedCutoff=CUTOFF_NM * unit.nanometer,
        )
        self.n_particles = self._system.getNumParticles()
        self.n_constraints = self._system.getNumConstraints()
        self.n_dof = 3 * self.n_particles - self.n_constraints - 3
        self.n_atoms = self.n_particles

        # Seed the atom-index maps (CA for RMSD, heavy for Rg/SASA).
        heavy_radii: list[float] = []
        for atom in self.modeller.topology.atoms():
            self._atom_to_residue[atom.index] = f"{atom.residue.name}{atom.residue.id}"
            if atom.name == "CA":
                self._ca_indices.append(atom.index)
            symbol = atom.element.symbol if atom.element is not None else "X"
            if symbol != "H":
                self._heavy_indices.append(atom.index)
                heavy_radii.append(_VDW_RADII.get(symbol, 1.5))
        self._heavy_radii = np.array(heavy_radii, dtype=np.float64) if heavy_radii else None

    def _simulation(self, platform_name: str | None = None):
        """Build (once) the Simulation, reusing the System built at init."""
        from openmm.app import Simulation
        from openmm import LangevinMiddleIntegrator, unit, Platform

        if self.simulation is not None:
            return self.simulation

        integrator = LangevinMiddleIntegrator(
            self.temperature_k * unit.kelvin,
            1 / unit.picosecond,
            TIMESTEP_FS * unit.femtoseconds,
        )
        cpu_threads = min(int(os.environ.get("OPENMM_CPU_THREADS", os.cpu_count() or 2)), 16)
        os.environ.setdefault("OPENMM_CPU_THREADS", str(cpu_threads))
        try:
            Platform.getPlatformByName("CPU").setPropertyDefaultValue("Threads", str(cpu_threads))
        except Exception:
            pass
        platform = Platform.getPlatformByName(platform_name) if platform_name else None
        self.simulation = Simulation(self.modeller.topology, self._system, integrator, platform=platform)
        self.simulation.context.setPositions(self.modeller.positions)
        self.simulation.context.setVelocitiesToTemperature(self.temperature_k)
        self.platform_used = self.simulation.context.getPlatform().getName()
        return self.simulation

    # ------------------------------------------------------------------
    # Energy minimization (Module 6)
    # ------------------------------------------------------------------

    def minimize(self, max_steps: int = 500) -> tuple[dict, dict]:
        from openmm import unit

        sim = self._simulation()
        try:
            forces = sim.context.getState(getForces=True).getForces(asNumpy=True)
            forces = np.asarray(forces.value_in_unit(unit.kilojoule_per_mole / unit.nanometer))
            init_max_force = float(np.max(np.linalg.norm(forces, axis=1)))
        except Exception:
            init_max_force = None

        t0 = time.time()
        sim.minimizeEnergy(maxIterations=max_steps)
        elapsed = round(time.time() - t0, 1)

        st = sim.context.getState(getEnergy=True, getForces=True, getPositions=True)
        energy = st.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
        try:
            f = np.asarray(st.getForces(asNumpy=True).value_in_unit(unit.kilojoule_per_mole / unit.nanometer))
            max_force = float(np.max(np.linalg.norm(f, axis=1)))
        except Exception:
            max_force = None

        coords = _positions_to_np(st.getPositions())
        self._ref_coords = coords
        init_coords = _positions_to_np(self.modeller.positions)
        if self._ca_indices:
            drift = _kabsch_rmsd(init_coords[self._ca_indices], coords[self._ca_indices])
        else:
            drift = 0.0

        data = {
            "steps": max_steps,
            "energy_kj_mol": round(energy, 2),
            "max_force_kj_mol_nm": round(max_force, 2) if max_force is not None else None,
            "init_max_force_kj_mol_nm": round(init_max_force, 2) if init_max_force is not None else None,
            "elapsed_seconds": elapsed,
            "drift_angstrom": round(drift, 3),
            "nan": not (math.isfinite(energy) and (max_force is None or math.isfinite(max_force))),
        }
        metrics = {
            "energy_finite": 1 if (math.isfinite(energy) and (max_force is None or math.isfinite(max_force))) else 0,
            "energy_bounded": 1 if math.isfinite(energy) and abs(energy) < 1e8 else 0,
        }
        return _to_native(data), metrics

    # ------------------------------------------------------------------
    # NVT equilibration (Module 7)
    # ------------------------------------------------------------------

    def nvt(self, steps: int | None = None) -> tuple[dict, dict]:
        from openmm import unit

        sim = self._simulation()
        steps = steps or self._nvt_steps or NVT_STEPS
        # Burn-in: let the thermostat establish the target regime before we
        # sample, so the gate measures equilibrium temperature, not the cold
        # equilibration transient.
        burn_in = steps // 2
        sim.step(burn_in)

        self.eq_temperature = []
        sample_steps = steps - burn_in
        chunk = max(sample_steps // 20, 1)
        for _ in range(max(sample_steps // chunk, 1)):
            sim.step(chunk)
            st = sim.context.getState(getEnergy=True)
            pe = st.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
            ke = st.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole)
            temp = _temperature_from_ke(ke, self.n_dof)
            done = burn_in + len(self.eq_temperature) * chunk + chunk
            self.eq_temperature.append({"step": done, "temperature_k": round(temp, 1), "kinetic_kj_mol": round(ke, 2)})

        temps = [p["temperature_k"] for p in self.eq_temperature]
        mean_temp = float(np.mean(temps)) if temps else None
        sd_temp = float(np.std(temps)) if temps else None
        drift = abs((mean_temp or 0.0) - self.temperature_k)
        finite = all(math.isfinite(t) for t in temps)
        # Fractional (relative) temperature stability: size-independent, so a
        # small protein with inherently larger thermal fluctuation is not
        # unfairly failed by an absolute-Kelvin threshold.
        cv_temp = (sd_temp / mean_temp) if (sd_temp is not None and mean_temp) else None

        data = {
            "steps": steps,
            "target_temperature_k": self.temperature_k,
            "mean_temperature_k": round(mean_temp, 1) if mean_temp is not None else None,
            "temperature_sd_k": round(sd_temp, 2) if sd_temp is not None else None,
            "temperature_cv": round(cv_temp, 4) if cv_temp is not None else None,
            "temperature_drift_k": round(drift, 1) if mean_temp is not None else None,
            "temperature": self.eq_temperature,
            "finite": bool(finite),
        }
        metrics = {
            "temperature_finite": 1 if finite else 0,
            "temperature_cv": round(cv_temp, 4) if cv_temp is not None else 0.0,
        }
        return _to_native(data), metrics

    # ------------------------------------------------------------------
    # NPT equilibration (Module 8) — not applicable in implicit solvent
    # ------------------------------------------------------------------

    def npt(self) -> tuple[dict, dict]:
        return {
            "applicable": False,
            "engine": "openmm",
            "solvent_mode": self.solvent_key.upper(),
            "reason": (
                "Pressure coupling (NPT) requires an explicit solvent box with periodic "
                "boundary conditions. This OpenMM path uses implicit solvent ("
                f"{self.solvent_key.upper()}), so NPT is not applicable. The GROMACS "
                "explicit-solvent path will run real NPT with barostat + Parrinello-Rahman."
            ),
        }, {"pressure_coupled": 0}

    # ------------------------------------------------------------------
    # Production MD (Module 9)
    # ------------------------------------------------------------------

    def _planned_production_steps(self) -> tuple[int, bool]:
        """Return (step_count, budget_clamped).

        The wall-clock budget is always honoured — even when the caller asks for
        an explicit length — so the synchronous endpoint never blocks a reverse
        proxy past its upstream timeout. ``budget_clamped`` tells the caller the
        requested length was cut to fit the budget.
        """
        rate = max(_EST_STEPS_PER_SEC / max(self.n_particles, 1), 1.0)
        max_by_time = int(rate * _PRODUCTION_BUDGET_SECONDS)
        floor = int(PRODUCTION_MIN_PS * 500)
        if self._production_steps is not None:
            planned = int(self._production_steps)
            cap = max(max_by_time, floor)
            return (planned if planned <= cap else cap), planned > cap
        target = int(PRODUCTION_TARGET_PS * 500)
        cap = int(PRODUCTION_MAX_PS * 500)
        return int(max(min(target, cap, max_by_time), floor)), False

    def produce(self) -> tuple[dict, dict]:
        from openmm import unit

        sim = self._simulation()
        steps, budget_clamped = self._planned_production_steps()

        if self._ref_coords is None:
            st = sim.context.getState(getEnergy=True, getPositions=True)
            self._ref_coords = _positions_to_np(st.getPositions())
        ref_ca = self._ref_coords[self._ca_indices] if self._ca_indices else self._ref_coords

        sim.step(100)  # warm up
        t0 = time.time()
        wall_budget_sec = _PRODUCTION_BUDGET_SECONDS
        self.frames = []
        self.frame_steps = []
        self.production_energy = []
        self.temperature_series = []
        self.rg_series = []

        n_target_frames = min(steps // 20, 60)
        step_interval = max(20, steps // max(n_target_frames, 1))
        wall_stopped = False

        done = 0
        while done < steps:
            if time.time() - t0 >= wall_budget_sec:
                wall_stopped = True
                break
            batch = min(step_interval, steps - done)
            sim.step(batch)
            done += batch
            st = sim.context.getState(getEnergy=True, getPositions=True)
            pe = st.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
            ke = st.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole)
            temp = _temperature_from_ke(ke, self.n_dof)
            self.production_energy.append(round(pe, 2))
            self.temperature_series.append({"step": done, "temperature_k": round(temp, 1), "kinetic_kj_mol": round(ke, 2)})
            coords = _positions_to_np(st.getPositions())
            self.frames.append(coords)
            self.frame_steps.append(done)
            if self._heavy_indices:
                self.rg_series.append({"step": done, "rg_angstrom": round(_radius_of_gyration(coords[self._heavy_indices]), 2)})
            else:
                self.rg_series.append({"step": done, "rg_angstrom": 0.0})

        elapsed = round(time.time() - t0, 1)
        final = sim.context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
        finite = all(math.isfinite(e) for e in self.production_energy) and math.isfinite(final)

        data = {
            "engine": "openmm",
            "platform": getattr(self, "platform_used", None),
            "production_steps": done,
            "requested_production_steps": steps,
            "production_ps": round(done / (1000.0 / TIMESTEP_FS), 1),
            "budget_clamped": bool(budget_clamped or wall_stopped),
            "wall_stopped": wall_stopped,
            "n_frames": len(self.frames),
            "final_energy_kj_mol": round(final, 2),
            "elapsed_seconds": elapsed,
            "n_atoms": self.n_particles,
        }
        metrics = {
            "production_frames": len(self.frames),
            "energy_finite": 1 if finite else 0,
        }
        return _to_native(data), metrics

    # ------------------------------------------------------------------
    # Trajectory QC (Module 10)
    # ------------------------------------------------------------------

    def trajectory_analysis(self) -> tuple[dict, dict]:
        ref_ca = self._ref_coords[self._ca_indices] if self._ca_indices else self._ref_coords

        rmsd = []
        for idx, coords in enumerate(self.frames):
            ca = coords[self._ca_indices] if self._ca_indices else coords
            rmsd.append({"frame": idx, "rmsd": round(_kabsch_rmsd(ref_ca, ca), 3)})

        rmsf = []
        if len(self.frames) >= 2:
            if self._ca_indices:
                ca_frames = [f[self._ca_indices] for f in self.frames]
                ca_ref = self._ref_coords[self._ca_indices]
                ca_to_res = {i: self._atom_to_residue[self._ca_indices[i]] for i in range(len(self._ca_indices))}
                rmsf = _compute_rmsf(ca_frames, ca_ref, ca_to_res)
            else:
                rmsf = _compute_rmsf(self.frames, self._ref_coords, self._atom_to_residue)

        rg_vals = [p["rg_angstrom"] for p in self.rg_series]
        rg_avg = round(float(np.mean(rg_vals)), 2) if rg_vals else None

        sasa_data = []
        if self._heavy_indices and self.frames:
            radii = self._heavy_radii
            n = min(len(self.frames), 4)
            idxs = np.linspace(0, len(self.frames) - 1, n).astype(int)
            for pi in idxs:
                sasa_data.append({"step": self.frame_steps[pi], "sasa_angstrom2": round(_sasa_shrake_ruger(self.frames[pi][self._heavy_indices], radii), 1)})
        sasa_avg = round(float(np.mean([p["sasa_angstrom2"] for p in sasa_data])) if sasa_data else None, 1)

        data = {
            "rmsd_basis": "CA" if self._ca_indices else "all_heavy",
            "rmsd": rmsd,
            "rmsd_avg_angstrom": round(float(np.mean([r["rmsd"] for r in rmsd])) if rmsd else 0.0, 3),
            "rmsd_final_angstrom": round(rmsd[-1]["rmsd"], 3) if rmsd else None,
            "rmsf": rmsf[:50],
            "rg_avg_angstrom": rg_avg,
            "sasa": sasa_data,
            "sasa_avg_angstrom2": sasa_avg,
            "protein_ligand": None,
            "note": "Trajectory QC computed over production frames (protein-only in v1; "
                    "protein-ligand H-bonds/contacts require a ligand parameterization step).",
        }
        metrics = {
            "rmsd_computed": 1 if len(rmsd) else 0,
            "rmsf_computed": 1 if rmsf else 0,
            "rg_computed": 1 if rg_vals else 0,
            "sasa_computed": 1 if sasa_data else 0,
        }
        return _to_native(data), metrics

    # ------------------------------------------------------------------
    # Convergence analysis (Module 11)
    # ------------------------------------------------------------------

    @staticmethod
    def _cv(values: list[float]) -> float | None:
        if len(values) < 2:
            return None
        arr = np.asarray(values, dtype=float)
        mean = float(arr.mean())
        if abs(mean) < 1e-9:
            return None
        return float(arr.std() / abs(mean))

    def convergence(self) -> tuple[dict, dict]:
        rmsd_vals = [_r["rmsd"] for _r in self._traj_rmsd()]
        rg_vals = [p["rg_angstrom"] for p in self.rg_series]
        energy_vals = list(self.production_energy)
        temp_vals = [p["temperature_k"] for p in self.temperature_series]

        checks = {
            "energy": self._cv(energy_vals),
            "temperature": self._cv(temp_vals),
            "rmsd": self._cv(rmsd_vals),
            "rg": self._cv(rg_vals),
        }

        table = []
        for name, cv in checks.items():
            if cv is None:
                status = "WARN"
            elif name == "temperature" and cv < 0.05:
                status = "PASS"
            elif name in ("energy", "rg") and cv < 0.05:
                status = "PASS"
            elif name == "rmsd" and cv < 0.35:
                status = "PASS"
            else:
                status = "WARN"
            table.append({"metric": name, "status": status, "cv": round(cv, 4) if cv is not None else None})
        # Independent-replica comparison is a separate advanced workflow.
        table.append({"metric": "independent_replica", "status": "WARN", "cv": None})

        overall = "PASS" if all(t["status"] == "PASS" for t in table) else "WARN"
        readiness = "ANALYSIS_READY" if overall == "PASS" else "ANALYSIS_READY_WITH_WARNINGS"

        data = {
            "convergence": table,
            "overall": overall,
            "readiness": readiness,
            "note": (
                "Convergence is judged by coefficient-of-variation stability of energy, "
                "temperature, RMSD and Rg over the trajectory. A trajectory finishing does "
                "not mean it is converged; short implicit runs typically finish "
                "ANALYSIS_READY_WITH_WARNINGS. Block analysis / ESS / replica comparison and "
                "free-energy methods (MM/PBSA, MM/GBSA, FEP, TI, umbrella sampling, "
                "metadynamics) are separate advanced workflows and are not auto-run.",
            ),
        }
        metrics = {f"converge_{t['metric']}": (1 if t["status"] == "PASS" else 0) for t in table}
        return _to_native(data), metrics

    def _traj_rmsd(self):
        ref_ca = self._ref_coords[self._ca_indices] if self._ca_indices else self._ref_coords
        out = []
        for idx, coords in enumerate(self.frames):
            ca = coords[self._ca_indices] if self._ca_indices else coords
            out.append({"frame": idx, "rmsd": _kabsch_rmsd(ref_ca, ca)})
        return out
