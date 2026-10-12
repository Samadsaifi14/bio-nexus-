"""Engine availability + selection for the MD pipeline (GROMACS + OpenMM seam).

The design supports GROMACS and OpenMM. OpenMM is the primary engine here (it is
installed and this is the exact path the force-field verification uses). GROMACS
(and the BioExcel BioBB wrappers) are a first-class second engine in the seam but
their availability is gated on the presence of binaries/packages, so a deployment
without GROMACS degrades honestly to OpenMM rather than failing.
"""

from __future__ import annotations

import logging
import shutil

logger = logging.getLogger(__name__)

_OPENMM_OK: bool | None = None
_GROMACS_OK: bool | None = None


def openmm_available() -> bool:
    global _OPENMM_OK
    if _OPENMM_OK is None:
        try:
            import openmm  # noqa: F401
            _OPENMM_OK = True
        except Exception as e:
            logger.warning("OpenMM unavailable: %s", e)
            _OPENMM_OK = False
    return _OPENMM_OK


def gromacs_available() -> bool:
    """True when a GROMACS binary (gmx/mdrun) is on PATH."""
    global _GROMACS_OK
    if _GROMACS_OK is None:
        _GROMACS_OK = bool(shutil.which("gmx") or shutil.which("mdrun"))
    return _GROMACS_OK


def engine_status() -> dict:
    """Availability + version report for the engine seam (module 4 gate)."""
    status: dict = {
        "primary": "openmm",
        "engines": {},
    }
    if openmm_available():
        import openmm
        status["engines"]["openmm"] = {
            "available": True,
            "version": getattr(openmm, "__version__", "unknown"),
        }
    else:
        status["engines"]["openmm"] = {"available": False}

    g = status["engines"]["gromacs"] = {
        "available": gromacs_available(),
        "bioBB": _biobb_any(),
    }
    if not g["available"]:
        g["note"] = (
            "GROMACS binary (gmx/mdrun) not found on PATH. The GROMACS and "
            "BioExcel BioBB paths are not run; the pipeline executes the OpenMM "
            "engine. Install GROMACS + biobb_gromacs/biobb_model/biobb_analysis "
            "to enable the explicit-solvent GROMACS workflow (real NPT, water box)."
        )
    return status


def _biobb_any() -> bool:
    for mod in ("biobb_io", "biobb_model", "biobb_gromacs", "biobb_analysis"):
        try:
            __import__(mod)
            return True
        except Exception:
            continue
    return False
