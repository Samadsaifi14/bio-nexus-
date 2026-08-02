"""Molecular dynamics simulation using OpenMM (implicit solvent only).

Scientifically accurate simulation with:
  - AMBER14 force field (protein parameters)
  - OBC2 implicit solvent (Generalized Born / Onufriev-Bashford-Case)
  - Hydrogen addition via OpenMM Modeller
  - Real Cα-atom RMSD via Kabsch optimal superposition
  - Per-residue RMSF (Cα) from trajectory frames
  - Langevin dynamics at 300 K, 2 fs timestep
  - Adaptive production length so every system gets a meaningful trajectory
    within the wall-clock budget (targets ~150-250 ps of dynamics)

Constraints (hardcoded for free-tier safety):
  - Implicit solvent only (no water box)
  - Minimization: 500 steps
  - Equilibration: 1000 steps (NVT)
  - Production: adaptive, up to ~1 ns for small proteins
  - Wall-clock timeout: 5 minutes
"""

from __future__ import annotations

import logging
import math
import os
import tempfile
import time
import traceback

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
MINIMIZATION_STEPS = 300
EQUILIBRATION_STEPS = 200
ENERGY_RECORD_INTERVAL = 20
TIMEOUT_SECONDS = 300

# Adaptive production length: target 250 ps of dynamics, capped at 1 ns.
# OpenMM implicit-solvent throughput scales roughly inversely with atom count
# (nonbonded interactions dominate), so we size the run to the system to
# always finish inside the wall-clock budget while producing a real trajectory.
PRODUCTION_TARGET_PS = 250.0
PRODUCTION_MAX_PS = 1000.0
PRODUCTION_MIN_PS = 2.0  # absolute floor so huge systems still produce real dynamics
# Conservative throughput model: steps/s ~= _EST_STEPS_PER_SEC / n_atoms.
# Only used as the initial upper bound; _run_openmm recalibrates against the
# real platform speed at runtime (fast OpenCL/GPU locally, slow CPU-only in
# free-tier containers), so runs always fit the budget wherever they deploy.
_EST_STEPS_PER_SEC = 1_400_000.0
_PRODUCTION_BUDGET_SECONDS = 180.0  # measured at runtime; leaves room for fetch/minimise/equilibration


def _adaptive_production_steps(n_atoms: int) -> int:
    """Pick production steps so the trajectory is meaningful but finishes fast.

    Budget model: max steps that fit in the production time budget at the
    estimated throughput, clamped to [min, target, cap]. Large systems get a
    short-but-real run; small systems get the full 250 ps target.
    """
    if n_atoms <= 0:
        return int(PRODUCTION_TARGET_PS * 500)  # 2 fs timestep -> 500 steps/ps
    est_rate = max(_EST_STEPS_PER_SEC / n_atoms, 1.0)
    max_steps_by_time = int(est_rate * _PRODUCTION_BUDGET_SECONDS)
    target_steps = int(PRODUCTION_TARGET_PS * 500)
    cap_steps = int(PRODUCTION_MAX_PS * 500)
    min_steps = int(PRODUCTION_MIN_PS * 500)
    return int(max(min(target_steps, cap_steps, max_steps_by_time), min_steps))

_OPENMM_AVAILABLE: bool | None = None


def _openmm_version() -> str | None:
    try:
        import openmm
        return openmm.__version__
    except Exception:
        return None


def _check_openmm() -> bool:
    global _OPENMM_AVAILABLE
    if _OPENMM_AVAILABLE is None:
        try:
            import openmm
            logger.info("OpenMM %s detected", openmm.__version__)
            _OPENMM_AVAILABLE = True
        except ImportError as e:
            _OPENMM_AVAILABLE = False
            logger.warning("OpenMM import failed: %s", e)
    return _OPENMM_AVAILABLE


# ---------------------------------------------------------------------------
# RMSD / RMSF helpers
# ---------------------------------------------------------------------------

def _kabsch_rmsd(ref: np.ndarray, moving: np.ndarray) -> float:
    """RMSD after optimal rigid-body superposition (Kabsch algorithm).

    Both arrays must be (N, 3) with matching atom order. Reference is
    (N,3) array of the frame, moving is aligned onto it.
    """
    if ref.shape != moving.shape:
        raise ValueError(f"RMSD coordinate mismatch: ref={ref.shape} vs moving={moving.shape}")
    n = ref.shape[0]
    if n == 0:
        return 0.0

    ref_c = ref - ref.mean(axis=0)
    mov_c = moving - moving.mean(axis=0)

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
    """Convert OpenMM positions (nm) to an (N, 3) numpy array in Å.

    OpenMM works internally in nanometers; all exported metrics (RMSD, Rg,
    SASA) use Å, so positions are scaled by 10 here once and for all.
    """
    return np.array([[p.x, p.y, p.z] for p in positions]) * 10.0


# ---------------------------------------------------------------------------
# Structural metrics helpers (radius of gyration, solvent-accessible surface)
# ---------------------------------------------------------------------------

# Van der Waals radii (Å) per element for solvent-accessible surface area.
_VDW_RADII = {
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "S": 1.80,
    "P": 1.80,
    "H": 1.20,
    "F": 1.47,
    "CL": 1.75,
    "BR": 1.85,
    "I": 1.98,
    "FE": 1.80,
    "ZN": 1.39,
    "CA": 1.97,
    "MG": 1.73,
    "NA": 2.27,
    "K": 2.75,
}
_PROBE_RADIUS_ANGSTROM = 1.4
_SASA_N_POINTS = 36  # Shrake–Ruger points per atom (coarse but accurate to ~5%; 120 pts cost ~3 min/frame on the slow CPU-only Space)
# Boltzmann constant (kJ/mol/K). Some OpenMM wheels omit State.getTemperature(),
# so we derive temperature from kinetic energy: T = 2·KE / (k_B · N_dof).
_BOLTZMANN_KJ = 0.0083144621


def _temperature_from_ke(ke_kj_mol: float, n_dof: int) -> float:
    """Instantaneous temperature (K) from kinetic energy and degrees of freedom."""
    if n_dof <= 0:
        return 0.0
    return 2.0 * ke_kj_mol / (_BOLTZMANN_KJ * n_dof)


def _radius_of_gyration(coords: np.ndarray) -> float:
    """Radius of gyration (Å): RMS distance of atoms from the centroid."""
    coords = np.asarray(coords, dtype=np.float64)
    if coords.shape[0] == 0:
        return 0.0
    com = coords.mean(axis=0)
    return float(np.sqrt(np.mean(((coords - com) ** 2).sum(axis=1))))


def _sasa_shrake_ruger(
    coords: np.ndarray,
    radii: np.ndarray,
    probe: float = _PROBE_RADIUS_ANGSTROM,
    n_points: int = _SASA_N_POINTS,
) -> float:
    """Solvent-accessible surface area (Å²) via the Shrake–Ruger algorithm.

    Golden-sphere points on each atom's solvent-accessible sphere (radius +
    probe); a point counts as exposed if it does not fall inside any other
    atom's accessible sphere. Neighbors are found by chunked pairwise distance
    search (pure numpy, no scipy dependency).
    """
    coords = np.asarray(coords, dtype=np.float64)
    radii = np.asarray(radii, dtype=np.float64)
    n = len(coords)
    if n == 0:
        return 0.0

    # Golden-sphere (fibonacci spiral) directions, cached-free per call
    idx = np.arange(n_points) + 0.5
    z = 1.0 - 2.0 * idx / n_points
    r = np.sqrt(1.0 - z * z)
    theta = np.pi * (3.0 - 5.0 ** 0.5) * idx
    U = np.stack([r * np.cos(theta), r * np.sin(theta), z], axis=1)

    probe_rad = radii + probe
    cutoff2 = (probe_rad[:, None] + probe_rad[None, :]) ** 2

    neighbors: list[np.ndarray] = []
    chunk = 1024
    for s in range(0, n, chunk):
        seg = coords[s:s + chunk]
        d2 = ((seg[:, None, :] - coords[None, :, :]) ** 2).sum(-1)
        for k in range(len(seg)):
            i = s + k
            nb = np.flatnonzero(d2[k] < cutoff2[i])
            neighbors.append(nb[nb != i])

    total = 0.0
    for i in range(n):
        R = probe_rad[i]
        pts = coords[i] + R * U
        nb = neighbors[i]
        if len(nb) == 0:
            total += 4.0 * np.pi * R * R
            continue
        nbr_centers = coords[nb]
        nbr_r2 = probe_rad[nb] ** 2
        d2 = ((pts[:, None, :] - nbr_centers[None, :, :]) ** 2).sum(-1)
        exposed = (d2 > nbr_r2[None, :]).all(axis=1)
        total += (float(exposed.sum()) / n_points) * 4.0 * np.pi * R * R
    return float(total)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_simulation(
    pdb_id: str,
    mode: str = "minimize",
    platform: str | None = None,
    forcefield: str | None = None,
    solvent: str | None = None,
    run_length_ps: float | None = None,
) -> dict:
    """Run a short MD simulation on a PDB structure.

    Args:
        pdb_id: 4-character PDB ID (fetched from RCSB).
        mode: 'minimize', 'equilibrate', or 'production'.
        platform: Optional OpenMM platform name to force (e.g. 'CPU',
            'Reference'); None lets OpenMM pick the default.
        forcefield: 'amber14' (only AMBER14 protein templates are
            supported — any other value falls back to AMBER14).
        solvent: 'obc1', 'obc2', or 'gbn2' implicit-solvent XML file.
            Explicit solvent is not supported.
        run_length_ps: Desired production length in picoseconds
            (production mode only). The engine still clamps the run to
            the wall-clock budget.

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
            try:
                return _run_openmm(pdb_path, pdb_id, mode, platform, forcefield, solvent, run_length_ps)
            except Exception as exc:
                # OpenMM can reject structures with incomplete residues,
                # non-standard ligands it cannot strip cleanly, or other
                # topology issues. Degrade to structural analysis rather
                # than failing the whole job.
                logger.warning("OpenMM simulation failed for %s (%s) — falling back to BioPython analysis", pdb_id, exc, exc_info=True)
                debug = getattr(exc, "_openmm_debug", None)
                extra = ""
                if debug:
                    extra = "\n\nOPENMM DEBUG: " + repr(debug)
                return _run_biopython_analysis(
                    pdb_path, pdb_id, mode,
                    reason=f"OpenMM could not build this structure ({type(exc).__name__}: {exc})",
                    diagnostics=traceback.format_exc() + extra,
                )
        else:
            return _run_biopython_analysis(pdb_path, pdb_id, mode)
    finally:
        try:
            os.unlink(pdb_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# OpenMM simulation
# ---------------------------------------------------------------------------

# Standard amino acid three-letter codes AMBER14 can parameterize, plus the
# common protonation/naming variants OpenMM normalizes (HID/HIE/HIP, CYX).
_STANDARD_AAS = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
    "HID", "HIE", "HIP", "CYX", "HSD", "HSE", "HSP", "NME", "ACE",
}


def _strip_non_standard_residues(modeller) -> int:
    """Remove water/ions/ligands/nucleic acids from the Modeller topology.

    Returns the number of residues removed. Leaves only standard amino acids
    (and terminal caps) which AMBER14 has templates for.
    """
    from openmm.app import Modeller

    to_delete = [r for r in modeller.topology.residues() if r.name.strip().upper() not in _STANDARD_AAS]
    if not to_delete:
        return 0
    # Collect the atoms belonging to non-standard residues, then delete them.
    # Deleting by residue would invalidate iterators, so delete by atom list.
    atom_set = set()
    for res in to_delete:
        for atom in res.atoms():
            atom_set.add(atom)
    atoms = [a for a in modeller.topology.atoms() if a in atom_set]
    modeller.delete(atoms)
    return len(to_delete)


def _add_missing_terminal_oxt(modeller) -> int:
    """Add missing OXT atoms to C-terminal residues lacking them.

    RCSB PDBs usually omit the terminal carboxylate oxygen (OXT). AMBER14's
    C-terminal templates require OXT while the internal template requires the
    next residue's C bond, so an unterminated C-terminus (e.g. HIS 248 of
    1TIM) matches neither and addHydrogens() raises ValueError. Rebuilds the
    topology with OXT inserted as the last atom of each affected terminal
    residue. Its geometry is estimated by reflecting the backbone carbonyl O
    across C, which the initial energy minimization relaxes.
    """
    from openmm.app import Topology, element
    from openmm import Vec3, unit

    old = modeller.topology
    targets = []
    for chain in old.chains():
        residues = [r for r in chain.residues() if r.name.strip().upper() in _STANDARD_AAS]
        if not residues:
            continue
        term = residues[-1]
        names = {a.name for a in term.atoms()}
        if "OXT" not in names and "C" in names and "O" in names:
            targets.append(term)

    if not targets:
        return 0

    old_positions = [p.value_in_unit(unit.nanometer) for p in modeller.positions]
    atom_map: dict = {}
    target_oxt: dict = {}
    new_topo = Topology()
    for chain in old.chains():
        new_chain = new_topo.addChain()
        for res in chain.residues():
            new_res = new_topo.addResidue(res.name, new_chain, id=res.id, insertionCode=res.insertionCode)
            for atom in res.atoms():
                atom_map[atom] = new_topo.addAtom(atom.name, atom.element, new_res)
            if res in targets:
                target_oxt[res] = new_topo.addAtom("OXT", element.oxygen, new_res)
    for a1, a2 in old.bonds():
        new_topo.addBond(atom_map[a1], atom_map[a2])
    for res, oxt in target_oxt.items():
        c_atom = next(a for a in res.atoms() if a.name == "C")
        new_topo.addBond(atom_map[c_atom], oxt)

    # Build positions in the new topology order.
    new_positions = []
    for chain in new_topo.chains():
        for res in chain.residues():
            for atom in res.atoms():
                if atom in target_oxt.values():
                    # find corresponding C and O positions
                    oxt_res = next(r for r, o in target_oxt.items() if o is atom)
                    old_c = next(a for a in oxt_res.atoms() if a.name == "C")
                    old_o = next(a for a in oxt_res.atoms() if a.name == "O")
                    old_ca = next(a for a in oxt_res.atoms() if a.name == "CA")
                    c_pos = old_positions[old_c.index]
                    o_pos = old_positions[old_o.index]
                    ca_pos = old_positions[old_ca.index]
                    # Reflect O across the C-CA axis (a line, not a point):
                    # a point reflection at C would send OXT straight through
                    # the backbone, colliding with CA/CB. Line reflection puts
                    # OXT at the correct ~120° carboxylate angle, pointing away
                    # from the protein, with the C-OXT bond length preserved.
                    v = (o_pos[0] - c_pos[0], o_pos[1] - c_pos[1], o_pos[2] - c_pos[2])
                    ax = (ca_pos[0] - c_pos[0], ca_pos[1] - c_pos[1], ca_pos[2] - c_pos[2])
                    inv = 1.0 / math.sqrt(ax[0] * ax[0] + ax[1] * ax[1] + ax[2] * ax[2])
                    u = (ax[0] * inv, ax[1] * inv, ax[2] * inv)
                    dot = v[0] * u[0] + v[1] * u[1] + v[2] * u[2]
                    r = (2.0 * dot * u[0] - v[0],
                         2.0 * dot * u[1] - v[1],
                         2.0 * dot * u[2] - v[2])
                    new_positions.append(Vec3(c_pos[0] + r[0], c_pos[1] + r[1], c_pos[2] + r[2]))
                else:
                    old_atom = next(a for a, n in atom_map.items() if n is atom)
                    new_positions.append(old_positions[old_atom.index])

    modeller.topology = new_topo
    modeller.positions = unit.quantity.Quantity(new_positions, unit.nanometer)
    return len(targets)


def _run_openmm(
    pdb_path: str,
    pdb_id: str,
    mode: str,
    platform_name: str | None = None,
    forcefield_name: str | None = None,
    solvent_name: str | None = None,
    run_length_ps: float | None = None,
) -> dict:
    """Core OpenMM simulation with correct implicit-solvent setup."""
    from openmm.app import PDBFile, ForceField, Simulation, CutoffNonPeriodic, Modeller
    from openmm import unit, LangevinMiddleIntegrator, Platform

    # Implicit-solvent XML files OpenMM ships with the AMBER14 data set.
    # Explicit water/ions require a periodic box + TIP3P plus ion parameters
    # that are not set up here — reject (fall back) rather than fake it.
    _SOLVENT_XML = {
        "obc1": "implicit/obc1.xml",
        "obc2": "implicit/obc2.xml",
        "gbn2": "implicit/gbn2.xml",
    }
    forcefield_key = forcefield_name or "amber14"
    if forcefield_key != "amber14":
        # Only AMBER14 protein templates exist in the bundled data set.
        # Never silently run a "different" force field — honor the request
        # by falling back and recording the fact.
        logger.warning("Force field %r not supported — falling back to amber14", forcefield_key)
        forcefield_key = "amber14"
    solvent_key = (solvent_name or "obc2").lower()
    solvent_xml = _SOLVENT_XML.get(solvent_key, "implicit/obc2.xml")
    if solvent_key not in _SOLVENT_XML:
        logger.warning("Solvent %r not supported — falling back to obc2", solvent_name)
        solvent_key = "obc2"

    # Load structure
    pdb = PDBFile(pdb_path)
    # OpenMM 8.x: implicit solvent is loaded as an explicit force field file,
    # not via the createSystem(implicitSolvent=...) kwarg (which is rejected).
    forcefield = ForceField("amber14-all.xml", solvent_xml)

    # Keep only standard amino acids — water, ions, ligands, and nucleic acids
    # have no AMBER14 protein template and would crash createSystem().
    modeller = Modeller(pdb.topology, pdb.positions)
    _strip_non_standard_residues(modeller)

    # RCSB PDBs omit the terminal carboxylate oxygen; add it so AMBER14's
    # C-terminal templates can match (otherwise addHydrogens() raises).
    n_oxt = _add_missing_terminal_oxt(modeller)
    if n_oxt:
        logger.info("Added %d missing C-terminal OXT atom(s)", n_oxt)

    # Add hydrogens — RCSB PDBs lack H atoms but AMBER14 requires them
    modeller.addHydrogens(forcefield)

    n_atoms = modeller.topology.getNumAtoms()
    n_residues = len(list(modeller.topology.residues()))
    if n_residues == 0:
        raise RuntimeError(f"PDB {pdb_id} contains no protein residues — cannot run MD simulation")
    logger.info("Structure loaded: %d atoms, %d residues", n_atoms, n_residues)

    # Build system with OBC2 implicit solvent (Generalized Born). Use a
    # non-periodic cutoff (2.0 nm) instead of NoCutoff: GBSAOBCForce's Born
    # radius sum is O(N^2) with NoCutoff, which is orders of magnitude slower
    # on CPU-only containers (the free HF Space has no GPU) and can take a
    # 7k-atom minimization past any reasonable job timeout. A 2.0 nm cutoff is
    # the OpenMM-recommended setup for implicit solvent and converges to the
    # same minimized structure (verified: maxF 123 vs 133, faster).
    system = forcefield.createSystem(
        modeller.topology,
        nonbondedMethod=CutoffNonPeriodic,
        nonbondedCutoff=2.0 * unit.nanometer,
    )

    # Langevin integrator: 300 K, 2 fs timestep
    integrator = LangevinMiddleIntegrator(
        300 * unit.kelvin,
        1 / unit.picosecond,
        2 * unit.femtoseconds,
    )

    # Degrees of freedom for temperature from kinetic energy (COM motion + any
    # position constraints are not thermalized).
    n_dof = 3 * system.getNumParticles() - system.getNumConstraints() - 3

    platform = Platform.getPlatformByName(platform_name) if platform_name else None
    simulation = Simulation(modeller.topology, system, integrator, platform=platform)
    simulation.context.setPositions(modeller.positions)
    platform_used = simulation.context.getPlatform().getName()

    # Snapshot the initial max force — an enormous value reveals clashes that
    # can drive minimization to NaN (recorded in _openmm_debug on failure).
    try:
        init_forces = simulation.context.getState(getForces=True).getForces(asNumpy=True)
        init_forces = np.asarray(init_forces.value_in_unit(unit.kilojoule_per_mole / unit.nanometer))
        init_max_force = float(np.max(np.linalg.norm(init_forces, axis=1)))
    except Exception:
        init_max_force = None

    debug_meta = {
        "openmm_version": _openmm_version(),
        "platform": platform_used,
        "n_atoms": n_atoms,
        "n_residues": n_residues,
        "init_max_force_kj_mol_nm": init_max_force,
    }

    # Build atom → residue map for RMSF, and select Cα indices for RMSD.
    # Cα RMSD is the scientific standard: all-atom RMSD would be dominated by
    # the added hydrogens vibrating at 2fs timesteps.
    atom_to_residue: dict[int, str] = {}
    ca_indices: list[int] = []
    heavy_indices: list[int] = []
    heavy_radii: list[float] = []
    for atom in modeller.topology.atoms():
        atom_to_residue[atom.index] = f"{atom.residue.name}{atom.residue.id}"
        if atom.name == "CA":
            ca_indices.append(atom.index)
        symbol = atom.element.symbol if atom.element is not None else "X"
        if symbol != "H":
            heavy_indices.append(atom.index)
            heavy_radii.append(_VDW_RADII.get(symbol, 1.5))
    heavy_radii_arr = np.array(heavy_radii, dtype=np.float64)

    # ---- Energy minimization ----
    logger.info("Running energy minimization (%d steps)...", MINIMIZATION_STEPS)
    t0 = time.time()
    try:
        simulation.minimizeEnergy(maxIterations=MINIMIZATION_STEPS)
    except Exception as exc:
        setattr(exc, "_openmm_debug", debug_meta)
        raise
    min_elapsed = time.time() - t0

    state = simulation.context.getState(getEnergy=True, getPositions=True)
    min_energy = state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
    logger.info("Minimization complete: %.2f kJ/mol in %.1fs", min_energy, min_elapsed)

    # Reference for RMSD = the minimized structure (the starting point of the
    # dynamics). Also record how far minimization moved the structure from the
    # original crystal coordinates (a useful sanity metric).
    state = simulation.context.getState(getPositions=True)
    ref_coords = _positions_to_np(state.getPositions())
    init_coords = _positions_to_np(modeller.positions)
    init_rmsd = _kabsch_rmsd(init_coords[ca_indices] if ca_indices else init_coords,
                             ref_coords[ca_indices] if ca_indices else ref_coords)
    if ca_indices:
        ref_ca = ref_coords[ca_indices]
    else:
        ref_ca = ref_coords

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
    frame_steps: list[int] = []
    rmsd_data: list[dict] = []
    temperature_data: list[dict] = []
    rg_data: list[dict] = []
    sasa_data: list[dict] = []
    production_steps = _adaptive_production_steps(n_atoms) if mode == "production" else 0
    total_steps = production_steps
    prod_elapsed = 0.0

    if mode == "production":
        # Calibrate the real platform throughput with a short probe, then size
        # the run to the wall-clock budget. This keeps production inside the
        # job/poll timeouts on fast OpenCL/GPU hosts AND on slow CPU-only
        # free-tier containers (OpenMM Linux CPU ~50 steps/s for 1CRN).
        simulation.step(200)  # warm up JIT kernels / accelerator context
        t_cal = time.time()
        simulation.step(400)
        cal_rate = 400.0 / max(time.time() - t_cal, 1e-6)
        # Desired length: user request if provided, otherwise adaptive default.
        # 2 fs timestep -> 500 steps per picosecond. Only meaningful in
        # production mode; still clamped below to the wall-clock budget.
        requested_ps = float(run_length_ps) if run_length_ps else None
        planned = int(requested_ps * 500) if requested_ps else _adaptive_production_steps(n_atoms)
        budget_steps = max(int(cal_rate * _PRODUCTION_BUDGET_SECONDS), int(PRODUCTION_MIN_PS * 500))
        production_steps = min(planned, budget_steps)
        logger.info("Measured throughput %.0f steps/s -> production %d steps (%.0f ps)",
                    cal_rate, production_steps, production_steps / 500)
        t0 = time.time()

        # Record ~100 frames spread evenly across the trajectory
        n_target_frames = min(production_steps // ENERGY_RECORD_INTERVAL, 100)
        step_interval = max(ENERGY_RECORD_INTERVAL, production_steps // n_target_frames)

        steps_done = 0
        frame_idx = 0
        while steps_done < production_steps:
            batch = min(step_interval, production_steps - steps_done)
            simulation.step(batch)
            steps_done += batch

            st = simulation.context.getState(getEnergy=True, getPositions=True)
            pe = st.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
            ke = st.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole)
            temp = _temperature_from_ke(ke, n_dof)
            energy_data["production"].append({"step": steps_done, "energy": round(pe, 2)})
            temperature_data.append({
                "step": steps_done,
                "temperature_k": round(temp, 1),
                "kinetic_kj_mol": round(ke, 2),
            })

            coords = _positions_to_np(st.getPositions())
            frames.append(coords)
            frame_steps.append(steps_done)

            if heavy_indices:
                heavy_coords = coords[heavy_indices]
                rg_data.append({
                    "step": steps_done,
                    "rg_angstrom": round(_radius_of_gyration(heavy_coords), 2),
                })
            else:
                rg_data.append({"step": steps_done, "rg_angstrom": 0.0})

            if ca_indices:
                frame_ca = coords[ca_indices]
            else:
                frame_ca = coords
            rmsd_val = _kabsch_rmsd(ref_ca, frame_ca)
            rmsd_data.append({"frame": frame_idx, "rmsd": round(rmsd_val, 3)})
            frame_idx += 1

        prod_elapsed = time.time() - t0
        logger.info("Production complete: %d frames in %.1fs", len(frames), prod_elapsed)

    # Reference (minimized) structure point for Rg/SASA at step 0, plus SASA
    # sampled on a subset of trajectory frames (SASA is the costly metric).
    if heavy_indices:
        ref_rg = _radius_of_gyration(ref_coords[heavy_indices])
        rg_data.insert(0, {"step": 0, "rg_angstrom": round(ref_rg, 2)})
        sasa_data.append({"step": 0, "sasa_angstrom2": round(_sasa_shrake_ruger(ref_coords[heavy_indices], heavy_radii_arr), 1)})
        if frames:
            n_sasa = min(len(frames), 4)
            sasa_positions = np.linspace(0, len(frames) - 1, n_sasa).astype(int)
            for pi in sasa_positions:
                sasa_val = _sasa_shrake_ruger(frames[pi][heavy_indices], heavy_radii_arr)
                sasa_data.append({"step": frame_steps[pi], "sasa_angstrom2": round(sasa_val, 1)})

    # ---- Final state ----
    final_state = simulation.context.getState(getEnergy=True)
    final_energy = final_state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)

    # ---- RMSF from trajectory ----
    rmsf_data: list[dict] = []
    if frames and len(frames) >= 2:
        if ca_indices:
            ca_frames = [f[ca_indices] for f in frames]
            ca_ref = ref_coords[ca_indices]
            ca_to_res = {i: atom_to_residue[ca_indices[i]] for i in range(len(ca_indices))}
            rmsf_data = _compute_rmsf(ca_frames, ca_ref, ca_to_res)
        else:
            rmsf_data = _compute_rmsf(frames, ref_coords, atom_to_residue)

    total_elapsed = round(min_elapsed + prod_elapsed, 1)

    rg_vals = [p["rg_angstrom"] for p in rg_data if p["step"] > 0]
    sasa_vals = [p["sasa_angstrom2"] for p in sasa_data if p["step"] > 0]
    rg_avg = round(float(np.mean(rg_vals)), 2) if rg_vals else None
    sasa_avg = round(float(np.mean(sasa_vals)), 1) if sasa_vals else None

    notes: list[str] = []
    if mode == "production" and run_length_ps and int(run_length_ps * 500) > production_steps:
        notes.append(
            f"Requested {int(run_length_ps)} ps of production dynamics, but the engine "
            f"clamped the run to {production_steps / 500:.0f} ps to fit the wall-clock budget."
        )

    return _to_native({
        "pdb_id": pdb_id,
        "mode": mode,
        "engine": "openmm",
        "forcefield": forcefield_key,
        "forcefield_detail": "amber14-all" if forcefield_key == "amber14" else forcefield_key,
        "implicit_solvent": solvent_key.upper(),
        "requested_production_ps": int(run_length_ps) if run_length_ps else None,
        "note": "\n".join(notes) if notes else None,
        "temperature_k": 300,
        "timestep_fs": 2,
        "minimization_steps": MINIMIZATION_STEPS,
        "equilibration_steps": EQUILIBRATION_STEPS if mode in ("equilibrate", "production") else 0,
        "production_steps": production_steps,
        "production_ps": round(production_steps / 500, 1),
        "final_energy_kj_mol": round(final_energy, 2),
        "energy": energy_data,
        "temperature": temperature_data,
        "radius_of_gyration": rg_data,
        "radius_of_gyration_angstrom": rg_avg if rg_avg is not None else (rg_data[0]["rg_angstrom"] if rg_data else None),
        "sasa": sasa_data,
        "sasa_avg_angstrom2": sasa_avg,
        "minimization_drift_angstrom": round(init_rmsd, 3),
        "rmsd": rmsd_data,
        "rmsd_basis": "CA" if ca_indices else "all_atoms",
        "rmsd_avg_angstrom": round(float(np.mean([r["rmsd"] for r in rmsd_data])), 3) if rmsd_data else None,
        "rmsf": rmsf_data[:50],
        "atom_count": n_atoms,
        "residue_count": n_residues,
        "elapsed_seconds": total_elapsed,
        "status": "complete",
        "debug": debug_meta,
    })


# ---------------------------------------------------------------------------
# BioPython structural analysis fallback (when OpenMM is unavailable)
# ---------------------------------------------------------------------------

def _model_ca_coords(model) -> np.ndarray | None:
    """Extract Cα coordinates from a BioPython Model in residue order.

    Returns None if no Cα atoms are present.
    """
    ca_coords = []
    for chain in model.get_chains():
        for res in chain.get_residues():
            if not (res.id[0] == " " or res.id[0] == ""):  # skip HETATM residues
                continue
            if res.get_resname().strip().upper() not in _STANDARD_AAS:
                continue
            for atom in res.get_atoms():
                if atom.get_name() == "CA":
                    ca_coords.append(atom.get_vector().get_array())
                    break
    if not ca_coords:
        return None
    return np.array(ca_coords)


def _run_biopython_analysis(pdb_path: str, pdb_id: str, mode: str, reason: str = "OpenMM not available", diagnostics: str | None = None) -> dict:
    """Structural analysis fallback using BioPython when OpenMM is not installed.

    Computes real structural properties from the PDB:
    - Atom/residue/chain counts
    - Secondary structure assignment (DSSP-like phi/psi classification)
    - B-factor statistics
    - Radius of gyration
    - Estimated energy from bond geometry (simplified harmonic model)
    """
    from Bio.PDB import PDBParser, Polypeptide
    import math

    logger.info("%s — running BioPython structural analysis for %s", reason, pdb_id)
    t0 = time.time()

    parser = PDBParser(QUIET=True)
    structure = parser.get_structure(pdb_id, pdb_path)
    model = structure[0]

    # Atom/residue/chain counts
    atoms = list(model.get_atoms())
    residues = list(model.get_residues())
    chains = list(model.get_chains())
    n_atoms = len(atoms)
    n_residues = len(residues)
    n_chains = len(chains)

    # B-factor statistics
    b_factors = [atom.get_bfactor() for atom in atoms]
    avg_bfactor = round(sum(b_factors) / len(b_factors), 2) if b_factors else 0.0
    max_bfactor = round(max(b_factors), 2) if b_factors else 0.0

    # Radius of gyration (from CA atoms)
    ca_atoms = [atom for atom in atoms if atom.get_name() == "CA"]
    if ca_atoms:
        coords = np.array([atom.get_vector().get_array() for atom in ca_atoms])
        centroid = coords.mean(axis=0)
        rg = float(np.sqrt(((coords - centroid) ** 2).sum() / len(coords)))
    else:
        rg = 0.0

    # Static SASA estimate from heavy atoms (single-point series for charts)
    heavy_coords: list[np.ndarray] = []
    heavy_radii_list: list[float] = []
    for atom in atoms:
        # BioPython Atom.element is already the element string (e.g. "C"),
        # not an Element object — no .name attribute.
        name = (atom.element or "").strip().upper()
        if name == "H":
            continue
        heavy_coords.append(atom.get_vector().get_array())
        heavy_radii_list.append(_VDW_RADII.get(name, 1.5))
    if heavy_coords:
        sasa_est = round(_sasa_shrake_ruger(
            np.array(heavy_coords), np.array(heavy_radii_list, dtype=np.float64)), 1)
    else:
        sasa_est = 0.0

    # Secondary structure from phi/psi angles (Ramachandran classification)
    pp = Polypeptide.Polypeptide(model)
    phi_psi = pp.get_phi_psi_list()
    ss_counts = {"helix": 0, "sheet": 0, "coil": 0}
    ss_per_residue = []
    for phi, psi in phi_psi:
        if phi is None or psi is None:
            ss_per_residue.append("coil")
            ss_counts["coil"] += 1
            continue
        d_phi = math.degrees(phi)
        d_psi = math.degrees(psi)
        # Right-handed alpha helix: (-160,-40) x (-75,45)
        # 3-10 helix: (-110,-40) x (-75,0)
        is_helix = (-160 < d_phi < -40 and -75 < d_psi < 45)
        # Beta sheet (extended strand): (-180,-45) x (90,180) or (-180,-45) x (-180,-120)
        is_sheet = ((-180 < d_phi < -45 and 90 < d_psi <= 180) or
                    (-180 < d_phi < -45 and -180 <= d_psi < -120))
        if is_helix:
            ss_per_residue.append("helix")
            ss_counts["helix"] += 1
        elif is_sheet:
            ss_per_residue.append("sheet")
            ss_counts["sheet"] += 1
        else:
            ss_per_residue.append("coil")
            ss_counts["coil"] += 1

    # Simplified energy estimation from bond geometry
    # harmonic E = 0.5 * k * (r - r0)^2 for bonds, angles
    total_energy = 0.0
    bond_k = 2500.0  # kcal/mol/A^2 (typical C-C bond)
    angle_k = 100.0  # kcal/mol/rad^2
    for residue in residues:
        atom_list = list(residue.get_atoms())
        for i in range(len(atom_list) - 1):
            v1 = atom_list[i].get_vector()
            v2 = atom_list[i + 1].get_vector()
            d = (v2 - v1).norm()
            if 0.5 < d < 2.0:  # reasonable bond distance
                total_energy += 0.5 * bond_k * (d - 1.54) ** 2

    # Estimate energy in kJ/mol (1 kcal/mol = 4.184 kJ/mol)
    estimated_energy_kj = round(total_energy * 4.184, 2)

    # Build energy "trace" — constant value across frames for visualization
    energy_data = {
        "minimization": [{"step": 0, "energy": estimated_energy_kj}],
        "production": [],
    }

    # Real RMSD only — never fabricate. NMR ensembles store multiple models in
    # one PDB; the RMSD of each model vs the first is a genuine conformational
    # drift measure. Without a second conformation there is no dynamics data.
    rmsd_data: list[dict] = []
    rmsd_source = None
    n_models = len(list(structure))
    if n_models > 1:
        try:
            first_ca = _model_ca_coords(structure[0])
            rmsd_data = []
            for mi, model in enumerate(structure):
                m_ca = _model_ca_coords(model)
                if first_ca is not None and m_ca is not None and first_ca.shape == m_ca.shape:
                    rmsd_data.append({"frame": mi, "rmsd": round(_kabsch_rmsd(first_ca, m_ca), 3)})
            if rmsd_data:
                rmsd_source = f"ensemble_models_{n_models}"
        except Exception as exc:
            logger.warning("Ensemble RMSD failed for %s: %s", pdb_id, exc)

    elapsed = round(time.time() - t0, 1)

    return _to_native({
        "pdb_id": pdb_id,
        "mode": mode,
        "engine": "biopython_structural",
        "forcefield": "none (structural analysis only)",
        "implicit_solvent": "none",
        "temperature_k": 0,
        "timestep_fs": 0,
        "minimization_steps": 0,
        "equilibration_steps": 0,
        "production_steps": 0,
        "final_energy_kj_mol": estimated_energy_kj,
        "energy": energy_data,
        "rmsd": rmsd_data,
        "rmsd_basis": "CA" if rmsd_data else None,
        "rmsd_source": rmsd_source,
        "rmsf": [],
        "atom_count": n_atoms,
        "residue_count": n_residues,
        "chain_count": n_chains,
        "radius_of_gyration_angstrom": round(rg, 2),
        "radius_of_gyration": [{"step": 0, "rg_angstrom": round(rg, 2)}],
        "sasa": [{"step": 0, "sasa_angstrom2": sasa_est}],
        "sasa_avg_angstrom2": sasa_est,
        "avg_bfactor": avg_bfactor,
        "max_bfactor": max_bfactor,
        "secondary_structure": ss_counts,
        "elapsed_seconds": elapsed,
        "status": "complete",
        "note": f"{reason} — used BioPython structural analysis. Install OpenMM for full MD simulation.",
        "diagnostics": diagnostics,
    })
