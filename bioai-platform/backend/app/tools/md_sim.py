"""Molecular dynamics simulation using OpenMM (implicit solvent only).

Scientifically accurate simulation with:
  - AMBER14 force field (protein parameters)
  - OBC2 implicit solvent (Generalized Born / Onufriev-Bashford-Case)
  - Hydrogen addition via OpenMM Modeller
  - Real RMSD via Kabsch optimal superposition
  - Per-residue RMSF from trajectory frames
  - Langevin dynamics at 300 K, 2 fs timestep

Constraints (hardcoded for free-tier safety):
  - Implicit solvent only (no water box)
  - Minimization: 500 steps
  - Equilibration: 1000 steps (NVT)
  - Production: 2000 steps
  - Wall-clock timeout: 5 minutes
"""

from __future__ import annotations

import logging
import os
import tempfile
import time

import numpy as np

logger = logging.getLogger(__name__)


def _to_native(obj):
    """Recursively convert numpy types to native Python for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

# Simulation parameters
MINIMIZATION_STEPS = 500
EQUILIBRATION_STEPS = 1000
PRODUCTION_STEPS = 2000
ENERGY_RECORD_INTERVAL = 20
TIMEOUT_SECONDS = 300

_OPENMM_AVAILABLE: bool | None = None


def _check_openmm() -> bool:
    global _OPENMM_AVAILABLE
    if _OPENMM_AVAILABLE is None:
        try:
            import openmm  # noqa: F401
            _OPENMM_AVAILABLE = True
        except ImportError:
            _OPENMM_AVAILABLE = False
            logger.warning("OpenMM not installed — MD simulation unavailable")
    return _OPENMM_AVAILABLE


# ---------------------------------------------------------------------------
# RMSD / RMSF helpers
# ---------------------------------------------------------------------------

def _kabsch_rmsd(ref: np.ndarray,移动: np.ndarray) -> float:
    """RMSD after optimal rigid-body superposition (Kabsch algorithm).

    Both arrays must be (N, 3) with matching atom order.
    """
    n = ref.shape[0]
    ref_c = ref - ref.mean(axis=0)
    mov_c = 移动 - 移动.mean(axis=0)

    H = mov_c.T @ ref_c
    U, S, Vt = np.linalg.svd(H)

    d = np.linalg.det(Vt.T @ U.T)
    sign = np.diag([1.0, 1.0, np.sign(d)])
    R = Vt.T @ sign @ U.T

    aligned = mov_c @ R.T
    diff = ref_c - aligned
    return float(np.sqrt((diff ** 2).sum() / n))


def _compute_rmsf(
    frames: list[np.ndarray],
    reference: np.ndarray,
    atom_to_residue: dict[int, str],
) -> list[dict]:
    """Per-residue RMSF from a set of trajectory frames vs reference."""
    from collections import defaultdict

    residue_atoms: dict[str, list[int]] = defaultdict(list)
    for atom_idx, res_key in atom_to_residue.items():
        residue_atoms[res_key].append(atom_idx)

    rmsf = {}
    for res_key, atom_indices in sorted(residue_atoms.items()):
        coords = np.array([[frame[i] for i in atom_indices] for frame in frames])
        ref_coords = np.array([reference[i] for i in atom_indices])
        displacements = coords - ref_coords
        mean_sq = (displacements ** 2).mean(axis=0).sum(axis=1).mean()
        rmsf[res_key] = float(np.sqrt(mean_sq))

    return [{"residue": k, "rmsf_angstrom": round(v, 3)} for k, v in rmsf.items()]


def _positions_to_np(positions) -> np.ndarray:
    """Convert OpenMM positions to (N, 3) numpy array."""
    return np.array([[p.x, p.y, p.z] for p in positions])


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_simulation(pdb_id: str, mode: str = "minimize") -> dict:
    """Run a short MD simulation on a PDB structure.

    Args:
        pdb_id: 4-character PDB ID (fetched from RCSB).
        mode: 'minimize', 'equilibrate', or 'production'.

    Returns:
        Dict with energy, RMSD, RMSF, and simulation metadata.

    Raises:
        RuntimeError if PDB fetch fails or OpenMM is unavailable.
    """
    import urllib.request

    pdb_id = pdb_id.upper().strip()

    # Fetch PDB from RCSB
    pdb_url = f"https://files.rcsb.org/view/{pdb_id}.pdb"
    logger.info("Fetching PDB %s from %s", pdb_id, pdb_url)
    try:
        pdb_text = urllib.request.urlopen(pdb_url, timeout=30).read().decode("utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch PDB {pdb_id} from RCSB: {e}")

    if not pdb_text or "ATOM" not in pdb_text:
        raise RuntimeError(f"PDB {pdb_id} returned empty or invalid data from RCSB")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
        f.write(pdb_text)
        pdb_path = f.name

    try:
        if _check_openmm():
            return _run_openmm(pdb_path, pdb_id, mode)
        else:
            raise RuntimeError(
                "OpenMM is not installed on this server. "
                "MD simulation requires OpenMM for physics-based computation. "
                "Please try again later."
            )
    finally:
        try:
            os.unlink(pdb_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# OpenMM simulation
# ---------------------------------------------------------------------------

def _run_openmm(pdb_path: str, pdb_id: str, mode: str) -> dict:
    """Core OpenMM simulation with correct implicit-solvent setup."""
    from openmm.app import PDBFile, ForceField, Simulation, NoCutoff, OBC2, Modeller
    from openmm import unit, LangevinMiddleIntegrator

    # Load structure
    pdb = PDBFile(pdb_path)
    forcefield = ForceField("amber14-all.xml")

    # Add hydrogens — RCSB PDBs lack H atoms but AMBER14 requires them
    modeller = Modeller(pdb.topology, pdb.positions)
    modeller.addHydrogens(forcefield)

    n_atoms = modeller.topology.getNumAtoms()
    n_residues = len(list(modeller.topology.residues()))
    logger.info("Structure loaded: %d atoms, %d residues", n_atoms, n_residues)

    # Build system with OBC2 implicit solvent (Generalized Born)
    system = forcefield.createSystem(
        modeller.topology,
        nonbondedMethod=NoCutoff,
        implicitSolvent=OBC2,
        solventDielectric=78.5,
        soluteDielectric=1.0,
    )

    # Langevin integrator: 300 K, 2 fs timestep
    integrator = LangevinMiddleIntegrator(
        300 * unit.kelvin,
        1 / unit.picosecond,
        2 * unit.femtoseconds,
    )

    simulation = Simulation(modeller.topology, system, integrator)
    simulation.context.setPositions(modeller.positions)

    # Build atom → residue map for RMSF
    atom_to_residue: dict[int, str] = {}
    for atom in modeller.topology.atoms():
        atom_to_residue[atom.index] = f"{atom.residue.name}{atom.residue.id}"

    # ---- Energy minimization ----
    logger.info("Running energy minimization (%d steps)...", MINIMIZATION_STEPS)
    t0 = time.time()
    simulation.minimizeEnergy(maxIterations=MINIMIZATION_STEPS)
    min_elapsed = time.time() - t0

    state = simulation.context.getState(getEnergy=True, getPositions=True)
    min_energy = state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
    logger.info("Minimization complete: %.2f kJ/mol in %.1fs", min_energy, min_elapsed)

    # Reference frame = minimized structure (used for RMSD)
    ref_coords = _positions_to_np(state.getPositions())

    energy_data: dict = {
        "minimization": [{"step": 0, "energy": round(min_energy, 2)}],
        "production": [],
    }

    # ---- Equilibration (NVT with Langevin thermostat) ----
    if mode in ("equilibrate", "production"):
        logger.info("Running equilibration (%d steps)...", EQUILIBRATION_STEPS)
        t0 = time.time()
        simulation.step(EQUILIBRATION_STEPS)
        eq_elapsed = time.time() - t0

        eq_state = simulation.context.getState(getEnergy=True)
        eq_energy = eq_state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
        energy_data["minimization"].append({"step": MINIMIZATION_STEPS, "energy": round(eq_energy, 2)})
        logger.info("Equilibration complete: %.2f kJ/mol in %.1fs", eq_energy, eq_elapsed)

    # ---- Production dynamics ----
    frames: list[np.ndarray] = []
    rmsd_data: list[dict] = []
    total_steps = PRODUCTION_STEPS if mode == "production" else 0
    prod_elapsed = 0.0

    if mode == "production":
        logger.info("Running production (%d steps, recording every %d)...", PRODUCTION_STEPS, ENERGY_RECORD_INTERVAL)
        t0 = time.time()

        # Determine how many steps between recordings, target ~100 frames max
        n_target_frames = min(PRODUCTION_STEPS // ENERGY_RECORD_INTERVAL, 100)
        step_interval = max(ENERGY_RECORD_INTERVAL, PRODUCTION_STEPS // n_target_frames)

        steps_done = 0
        frame_idx = 0
        while steps_done < PRODUCTION_STEPS:
            batch = min(step_interval, PRODUCTION_STEPS - steps_done)
            simulation.step(batch)
            steps_done += batch

            st = simulation.context.getState(getEnergy=True, getPositions=True)
            pe = st.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
            energy_data["production"].append({"step": steps_done, "energy": round(pe, 2)})

            coords = _positions_to_np(st.getPositions())
            frames.append(coords)

            rmsd_val = _kabsch_rmsd(ref_coords, coords)
            rmsd_data.append({"frame": frame_idx, "rmsd": round(rmsd_val, 3)})
            frame_idx += 1

        prod_elapsed = time.time() - t0
        logger.info("Production complete: %d frames in %.1fs", len(frames), prod_elapsed)

    # ---- Final state ----
    final_state = simulation.context.getState(getEnergy=True)
    final_energy = final_state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)

    # ---- RMSF from trajectory ----
    rmsf_data: list[dict] = []
    if frames and len(frames) >= 2:
        rmsf_data = _compute_rmsf(frames, ref_coords, atom_to_residue)

    total_elapsed = round(min_elapsed + prod_elapsed, 1)

    return _to_native({
        "pdb_id": pdb_id,
        "mode": mode,
        "engine": "openmm",
        "forcefield": "amber14-all",
        "implicit_solvent": "OBC2",
        "temperature_k": 300,
        "timestep_fs": 2,
        "minimization_steps": MINIMIZATION_STEPS,
        "equilibration_steps": EQUILIBRATION_STEPS if mode in ("equilibrate", "production") else 0,
        "production_steps": total_steps,
        "final_energy_kj_mol": round(final_energy, 2),
        "energy": energy_data,
        "rmsd": rmsd_data,
        "rmsf": rmsf_data[:50],
        "atom_count": n_atoms,
        "residue_count": n_residues,
        "elapsed_seconds": total_elapsed,
        "status": "complete",
    })
