"""Staged MD pipeline orchestration.

Reuses the platform's shared contract engine + ``Pipeline`` runner (used by the
NGS v2 assay pipeline) so the MD pipeline is literally built from the same
building blocks — "the same platform" for MD and NGS: every stage is a QC
contract with a decision, a STOP blocks downstream, and provenance is threaded
through a shared state dict.
"""

from __future__ import annotations

from app.ngs.orchestrator import Pipeline
from app.md.stages import (
    md_build_contract,
    md_convergence_contract,
    md_ff_contract,
    md_input_contract,
    md_minimize_contract,
    md_npt_contract,
    md_nvt_contract,
    md_prepare_contract,
    md_production_contract,
    md_traj_contract,
)

STAGE_INTRO = {
    "md_input": "Structure QC: validate PDB, count atoms/residues/chains, flag non-standard residues, waters, metals, missing OXT.",
    "md_ff": "Force-field compatibility gate: resolve and verify the (force field x solvent) pair; report GROMACS/BioBB availability.",
    "md_prepare": "Protein prep: strip non-standard residues, add C-terminal OXT, add hydrogens (Modeller). Ligand prep noted as separate.",
    "md_build": "System construction: build the OpenMM system (implicit solvent — no water box in this engine).",
    "md_minimize": "Energy minimization: remove clashes; STOP on NaN / exploding coordinates.",
    "md_nvt": "NVT equilibration: settle the thermostat; gate on finite + stable temperature.",
    "md_npt": "NPT equilibration: pressure coupling (not-applicable in implicit solvent; GROMACS explicit-solvent path runs real NPT).",
    "md_production": "Production MD: generate the trajectory + energy log.",
    "md_traj": "Trajectory QC: RMSD, RMSF, radius of gyration, SASA.",
    "md_convergence": "Convergence analysis: CV-stability of energy/temperature/RMSD/Rg + final readiness verdict.",
}


def build_md_pipeline() -> Pipeline:
    """Build the staged MD DAG (identical engine to the NGS v2 pipeline)."""
    pipe = Pipeline(name="md-protein-ligand", version="0.1.0")
    pipe.add_many([
        md_input_contract(),
        md_ff_contract(),
        md_prepare_contract(),
        md_build_contract(),
        md_minimize_contract(),
        md_nvt_contract(),
        md_npt_contract(),
        md_production_contract(),
        md_traj_contract(),
        md_convergence_contract(),
    ])
    return pipe
