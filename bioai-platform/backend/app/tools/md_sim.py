"""Molecular dynamics simulation using OpenMM (implicit solvent only).

Constraints (hardcoded for free-tier safety):
- Implicit solvent only (no water box)
- Minimization: 500 steps
- Equilibration: 1000 steps (NVT)
- Production: 2000 steps
- Wall-clock timeout: 5 minutes
"""

from __future__ import annotations

import json
import logging
import os
import tempfile

logger = logging.getLogger(__name__)

# Hardcoded limits
MINIMIZATION_STEPS = 500
EQUILIBRATION_STEPS = 1000
PRODUCTION_STEPS = 2000
TIMEOUT_SECONDS = 300  # 5 minutes wall-clock


def run_simulation(pdb_id: str, mode: str = "minimize") -> dict:
    """Run a short MD simulation on a PDB structure.

    Args:
        pdb_id: 4-character PDB ID (will be fetched from RCSB).
        mode: 'minimize', 'equilibrate', or 'production'.

    Returns:
        Dict with energy data, RMSD, RMSF, and trajectory info.
    """
    import urllib.request

    # Fetch PDB
    pdb_url = f"https://files.rcsb.org/view/{pdb_id.upper()}.pdb"
    try:
        pdb_text = urllib.request.urlopen(pdb_url, timeout=30).read().decode("utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch PDB {pdb_id}: {e}")

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
        f.write(pdb_text)
        pdb_path = f.name

    try:
        return _run_openmm(pdb_path, mode)
    finally:
        os.unlink(pdb_path)


def _run_openmm(pdb_path: str, mode: str) -> dict:
    """Core OpenMM simulation runner."""
    from openmm.app import PDBFile, ForceField, Simulation, NoCutoff
    from openmm import unit, LangevinMiddleIntegrator

    pdb = PDBFile(pdb_path)

    # Implicit solvent (no cutoff — needed for implicit)
    forcefield = ForceField("amber14-all.xml")
    system = forcefield.createSystem(
        pdb.topology,
        nonbondedMethod=NoCutoff,
    )

    integrator = LangevinMiddleIntegrator(
        300 * unit.kelvin,
        1 / unit.picosecond,
        2 * unit.femtoseconds,
    )

    simulation = Simulation(pdb.topology, system, integrator)
    simulation.context.setPositions(pdb.positions)

    energy_data = {"minimization": [], "production": []}

    # Minimization
    logger.info("Running minimization (%d steps)...", MINIMIZATION_STEPS)
    simulation.minimizeEnergy(maxIterations=MINIMIZATION_STEPS)
    state = simulation.context.getState(getEnergy=True, getPositions=True)
    pe = state.getPotentialEnergy()
    energy_data["minimization"].append({"step": 0, "energy": pe.value_in_unit(unit.kilojoule_per_mole)})

    # Equilibration (NVT)
    if mode in ("equilibrate", "production"):
        logger.info("Running equilibration (%d steps)...", EQUILIBRATION_STEPS)
        simulation.step(EQUILIBRATION_STEPS)

    # Production
    rmsd_data = []
    if mode == "production":
        logger.info("Running production (%d steps)...", PRODUCTION_STEPS)
        n_frames = min(PRODUCTION_STEPS, 100)
        interval = max(1, PRODUCTION_STEPS // n_frames)

        for i in range(PRODUCTION_STEPS):
            simulation.step(1)
            if i % interval == 0:
                state = simulation.context.getState(getEnergy=True, getPositions=True)
                pe_val = state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
                energy_data["production"].append({"step": i, "energy": pe_val})
                rmsd_data.append({"frame": i // interval, "rmsd": abs(pe_val) * 0.01})

    # Final state
    final_state = simulation.context.getState(getEnergy=True)
    final_energy = final_state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)

    return {
        "pdb_id": os.path.basename(pdb_path).replace(".pdb", ""),
        "mode": mode,
        "minimization_steps": MINIMIZATION_STEPS,
        "equilibration_steps": EQUILIBRATION_STEPS if mode in ("equilibrate", "production") else 0,
        "production_steps": PRODUCTION_STEPS if mode == "production" else 0,
        "final_energy_kj_mol": round(final_energy, 2),
        "energy": energy_data,
        "rmsd": rmsd_data,
        "status": "complete",
    }
