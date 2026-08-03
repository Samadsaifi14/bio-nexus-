"""MD force field / solvent configuration with startup verification.

The exposed menu of force fields and implicit-solvent models is not a static
list: every (force field x solvent) combination is verified at import time by
running a real OpenMM ``createSystem()`` on an embedded alanine-dipeptide
structure (the canonical test system), using the exact same construction path
as the simulation engine (PDBFile -> Modeller -> addHydrogens -> createSystem
with a non-periodic 2.0 nm cutoff). Only combinations that build successfully
are exposed through ``GET /api/md/forcefields`` and accepted by the run
endpoints. An unknown or unverified combination raises an explicit ValueError
instead of silently falling back to AMBER14/OBC2.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

# User-facing force field keys -> bundled OpenMM XML force field files.
FF_XML: dict[str, str] = {
    "amber14": "amber14-all.xml",                # legacy all-residue AMBER14
    "ff14sb": "amber14/protein.ff14SB.xml",
    "ff15ipq": "amber14/protein.ff15ipq.xml",
    "ff19sb": "amber19/protein.ff19SB.xml",
    "amberfb15": "amberfb15.xml",
    "charmm36": "charmm36.xml",
}

FF_LABELS: dict[str, str] = {
    "amber14": "AMBER14 (ff14SB)",
    "ff14sb": "AMBER ff14SB",
    "ff15ipq": "AMBER ff15ipq",
    "ff19sb": "AMBER ff19SB",
    "amberfb15": "AMBER ff15 (amberfb15)",
    "charmm36": "CHARMM36",
}

# Implicit-solvent (Generalized Born) models -> bundled XML files.
SOLVENT_XML: dict[str, str] = {
    "obc1": "implicit/obc1.xml",
    "obc2": "implicit/obc2.xml",
    "gbn2": "implicit/gbn2.xml",
}

DEFAULT_FORCEFIELD = "amber14"
DEFAULT_SOLVENT = "obc2"

# Heavy-atom alanine dipeptide (ALA-ALA with C-terminal OXT) used as the
# startup verification probe. It exercises the same Modeller/addHydrogens
# construction path the real simulation uses, is fully self-contained, and
# needs no network access. Its geometry is approximate; the probe only checks
# that createSystem() builds a valid System, so this is acceptable.
_DIPEPTIDE_PDB = """\
REMARK   1 CREATED WITH OPENMM 8.5.2
CRYST1   40.960   18.650   22.520  90.00  90.77  90.00 P 1           1
ATOM      1  N   ALA A   1      17.047  14.099   3.625  1.00  0.00           N
ATOM      2  CA  ALA A   1      16.967  12.784   4.338  1.00  0.00           C
ATOM      3  C   ALA A   1      15.685  12.755   5.133  1.00  0.00           C
ATOM      4  O   ALA A   1      15.268  13.825   5.594  1.00  0.00           O
ATOM      5  CB  ALA A   1      18.170  12.703   5.337  1.00  0.00           C
ATOM      6  N   ALA A   2      15.115  11.555   5.265  1.00  0.00           N
ATOM      7  CA  ALA A   2      13.856  11.469   6.066  1.00  0.00           C
ATOM      8  C   ALA A   2      14.164  10.785   7.379  1.00  0.00           C
ATOM      9  O   ALA A   2      14.993   9.862   7.443  1.00  0.00           O
ATOM     10  CB  ALA A   2      12.732  10.711   5.261  1.00  0.00           C
ATOM     11  OXT ALA A   2      13.343  11.699   7.316  1.00  0.00           O
TER      11      ALA A   2
END
"""

_VERIFIED: dict[str, tuple[str, ...]] | None = None
_VERIFY_ERRORS: dict[tuple[str, str], str] | None = None


def _build_dipeptide_system(forcefield: str, solvent: str) -> None:
    """Run the real construction path on the dipeptide (raises on failure)."""
    from openmm.app import PDBFile, ForceField, Modeller, CutoffNonPeriodic
    from openmm import unit

    pdb = PDBFile(io.StringIO(_DIPEPTIDE_PDB))
    forcefield_xml = ForceField(FF_XML[forcefield], SOLVENT_XML[solvent])
    modeller = Modeller(pdb.topology, pdb.positions)
    modeller.addHydrogens(forcefield_xml)
    forcefield_xml.createSystem(
        modeller.topology,
        nonbondedMethod=CutoffNonPeriodic,
        nonbondedCutoff=2.0 * unit.nanometer,
    )


def verify_ff_solvent_combos() -> dict[str, tuple[str, ...]]:
    """Verify every (force field x solvent) combo with a real createSystem().

    Returns a dict mapping each passing force field to the tuple of solvents
    it supports. Results are cached after the first call. When OpenMM is not
    installed, returns an empty mapping (MD degrades to structural analysis).
    """
    global _VERIFIED, _VERIFY_ERRORS
    if _VERIFIED is not None:
        return _VERIFIED

    verified: dict[str, list[str]] = {ff: [] for ff in FF_XML}
    errors: dict[tuple[str, str], str] = {}
    try:
        import openmm  # noqa: F401
    except Exception as e:
        logger.warning("OpenMM unavailable — MD force field verification skipped: %s", e)
        _VERIFIED = {}
        _VERIFY_ERRORS = {}
        return _VERIFIED

    for ff in FF_XML:
        for solvent in SOLVENT_XML:
            try:
                _build_dipeptide_system(ff, solvent)
                verified[ff].append(solvent)
            except Exception as exc:
                errors[(ff, solvent)] = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "MD combo %s x %s FAILED verification: %s: %s",
                    ff, solvent, type(exc).__name__, exc,
                )
    _VERIFIED = {ff: tuple(ff_solvents) for ff, ff_solvents in verified.items()}
    _VERIFY_ERRORS = errors
    logger.info(
        "MD force field verification complete: %d force fields, combos=%s",
        len(_VERIFIED), {ff: list(s) for ff, s in _VERIFIED.items()},
    )
    return _VERIFIED


def get_forcefields_menu() -> dict:
    """Menu payload for GET /api/md/forcefields (verified combos only)."""
    verified = verify_ff_solvent_combos()
    return {
        "forcefields": [
            {"value": ff, "label": FF_LABELS.get(ff, ff)}
            for ff in FF_XML
            if verified.get(ff)
        ],
        "solvents": [{"value": s, "label": f"Implicit · {s.upper()}"} for s in SOLVENT_XML],
        "combos": {ff: list(solvents) for ff, solvents in verified.items()},
        "defaults": {"forcefield": DEFAULT_FORCEFIELD, "solvent": DEFAULT_SOLVENT},
        "probe": {
            "system": "alanine dipeptide (ALA-ALA)",
            "forcefields_tested": len(FF_XML),
            "solvents_tested": len(SOLVENT_XML),
        },
    }


def resolve_combo(forcefield: str | None, solvent: str | None) -> tuple[str, str]:
    """Normalize and validate a requested (forcefield, solvent) pair.

    Raises ValueError with a clear message when the force field or solvent is
    unknown, or when the specific combination did not pass startup
    verification. No silent fallback: an invalid request is an explicit error.
    """
    ff_key = (forcefield or DEFAULT_FORCEFIELD).strip().lower()
    sol_key = (solvent or DEFAULT_SOLVENT).strip().lower()

    if ff_key not in FF_XML:
        raise ValueError(
            f"Unsupported force field: {forcefield!r}. Choose from: "
            + ", ".join(FF_XML)
        )
    if sol_key not in SOLVENT_XML:
        raise ValueError(
            f"Unsupported solvent model: {solvent!r}. Choose from: "
            + ", ".join(SOLVENT_XML)
        )

    verified = verify_ff_solvent_combos()
    if verified and sol_key not in verified.get(ff_key, ()):
        raise ValueError(
            f"Force field '{ff_key}' is not available with solvent '{sol_key}' "
            f"on this deployment. Supported solvents for '{ff_key}': "
            + (", ".join(verified.get(ff_key, ())) if verified.get(ff_key) else "none")
        )
    return ff_key, sol_key
