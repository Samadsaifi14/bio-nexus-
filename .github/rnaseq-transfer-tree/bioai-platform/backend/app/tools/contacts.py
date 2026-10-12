"""Intramolecular contacts within a single protein structure.

Structure preparation and CASTp operate on a bare receptor PDB with no ligand, so
ligand-style contacts (as reported by `app.routers.docking`) do not exist there. This
module reports the bonds that *are* defined for a ligand-free structure: internal
hydrogen bonds, salt bridges, hydrophobic core packing, and disulfide bridges.

All criteria are geometric heavy-atom cutoffs shared with the docking contact engine
(`app/routers/docking.py`) so both surfaces speak the same units. Results are
contacts, NOT energetics: no protonation states, solvent, or force fields are
implied, and every payload carries its criteria plus an explicit limitation string.
"""

import logging
import math
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ── criteria (angstroms / degrees) ─────────────────────────────────────────
HBOND_MAX_DISTANCE = 3.5
HBOND_MIN_ANGLE = 120.0
SALT_BRIDGE_MAX_DISTANCE = 4.0
HYDROPHOBIC_MAX_DISTANCE = 4.5
DISULFIDE_MAX_DISTANCE = 2.5

# Per-type output cap. Hydrophobic packing alone can exceed 10k pairs in a large
# protein; truncation is flagged in the payload rather than silently applied.
MAX_PER_TYPE = 2000

DONOR_ACCEPTOR_ELEMENTS = {"N", "O", "S"}
CATIONIC_RES = {"LYS", "ARG"}
ANIONIC_RES = {"ASP", "GLU"}

# Charged side-chain atoms: cationic N donors vs anionic O acceptors.
CATIONIC_NITROGENS = {"LYS": ("NZ",), "ARG": ("CZ", "NH1", "NH2")}
ANIONIC_OXYGENS = {"ASP": ("OD1", "OD2"), "GLU": ("OE1", "OE2")}

HYDROPHOBIC_RES = {"ALA", "VAL", "LEU", "ILE", "MET", "PHE", "TRP", "PRO", "GLY"}
HYDROPHOBIC_ELEMENTS = {"C", "S"}


class _Atom:
    __slots__ = ("name", "res_name", "chain", "res_seq", "element", "xyz")

    def __init__(self, name, res_name, chain, res_seq, element, xyz):
        self.name = name
        self.res_name = res_name
        self.chain = chain
        self.res_seq = res_seq
        self.element = element
        self.xyz = xyz

    @property
    def label(self) -> str:
        return f"{self.res_name}{self.res_seq}{self.chain}"


def _element_of(atom_name: str, element_field: str | None) -> str:
    if element_field:
        sym = element_field.strip().upper()
        if sym:
            return sym
    name = atom_name.strip().upper()
    if name[:1].isdigit():
        name = name[1:]
    return name[:1]


def _parse_atoms(pdb_text: str) -> list[_Atom]:
    """Parse ATOM/HETATM records by fixed PDB column offsets.

    Columns are used rather than whitespace splitting because the coordinate fields
    (cols 31-54) are exactly 8 characters wide: a value such as "1000.000" fills the
    field completely and leaves no separating blank to split on.
    """
    atoms: list[_Atom] = []
    for line in pdb_text.splitlines():
        if not (line.startswith("ATOM") or line.startswith("HETATM")):
            continue
        if len(line) < 54:
            continue
        try:
            coords = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
            res_seq = int(line[22:26])
        except ValueError:
            continue
        element_field = line[76:78] if len(line) >= 78 else None
        atoms.append(_Atom(
            name=line[12:16].strip().upper(),
            res_name=line[17:20].strip().upper(),
            chain=line[21].strip(),
            res_seq=res_seq,
            element=_element_of(line[12:16], element_field),
            xyz=coords,
        ))
    return atoms


def _neighbour_pairs(coords: np.ndarray, cutoff: float, chunk: int = 512):
    """Yield (i, j, distance) for all pairs within cutoff, i < j, chunked so a
    large structure never materialises a full NxN distance matrix."""
    n = len(coords)
    for start in range(0, n, chunk):
        stop = min(start + chunk, n)
        block = coords[start:stop]
        diff = block[:, None, :] - coords[None, :, :]
        dist = np.sqrt((diff * diff).sum(axis=2))
        rows, cols = np.nonzero(dist <= cutoff)
        for r, c in zip(rows, cols):
            i = start + int(r)
            j = int(c)
            if j > i:
                yield i, j, float(dist[r, c])


def _is_adjacent(a: _Atom, b: _Atom) -> bool:
    """Covalently bonded neighbours (same/adjacent sequence position in the same
    chain) are excluded: they are not non-covalent contacts."""
    if a.chain == b.chain and abs(a.res_seq - b.res_seq) <= 1:
        return True
    return a.chain == b.chain and a.res_seq == b.res_seq


def _angle_deg(a, b, c) -> float:
    ba = (a[0] - b[0], a[1] - b[1], a[2] - b[2])
    bc = (c[0] - b[0], c[1] - b[1], c[2] - b[2])
    dot = ba[0] * bc[0] + ba[1] * bc[1] + ba[2] * bc[2]
    mag_ba = math.sqrt(ba[0] ** 2 + ba[1] ** 2 + ba[2] ** 2)
    mag_bc = math.sqrt(bc[0] ** 2 + bc[1] ** 2 + bc[2] ** 2)
    if mag_ba < 1e-9 or mag_bc < 1e-9:
        return 0.0
    cos_angle = max(-1.0, min(1.0, dot / (mag_ba * mag_bc)))
    return math.degrees(math.acos(cos_angle))


def _hydrogen_atoms(atoms: list[_Atom]) -> list[_Atom]:
    return [a for a in atoms if a.element == "H"]


def _bond_angle_ok(donor: _Atom, acceptor: _Atom, distance: float,
                   hydrogens: list[_Atom]) -> bool:
    """Apply the donor-H...acceptor angle test when the structure carries explicit
    hydrogens. Without hydrogens (the common case for a cleaned receptor) the
    heavy-atom distance criterion stands alone and the caller records that."""
    attached = [
        h for h in hydrogens
        if h.res_name == donor.res_name and h.res_seq == donor.res_seq
        and h.chain == donor.chain
        and math.dist(h.xyz, donor.xyz) < 1.3
    ]
    if not attached:
        return True
    return any(_angle_deg(acceptor.xyz, h.xyz, donor.xyz) >= HBOND_MIN_ANGLE
               for h in attached)


def _collect(kind: str, rows: list[dict[str, Any]], total: int) -> dict[str, Any]:
    truncated = total > MAX_PER_TYPE
    if truncated:
        logger.warning("intramolecular %s contacts truncated: %d of %d", kind, MAX_PER_TYPE, total)
    return {
        "items": rows[:MAX_PER_TYPE],
        "count": min(total, MAX_PER_TYPE),
        "total": total,
        "truncated": truncated,
    }


def compute_intramolecular_contacts(pdb_text: str) -> dict[str, Any]:
    """Detect hydrogen bonds, salt bridges, hydrophobic core contacts, and
    disulfide bridges within a single structure.

    Returns a payload shaped like the docking interaction dict (`hbonds`,
    `salt_bridges`, `hydrophobic`, plus `disulfides`) so existing result surfaces
    can render it, with per-type totals/truncation flags and the criteria used.
    """
    atoms = _parse_atoms(pdb_text)
    if not atoms:
        return {
            "hbonds": {"items": [], "count": 0, "total": 0, "truncated": False},
            "salt_bridges": {"items": [], "count": 0, "total": 0, "truncated": False},
            "hydrophobic": {"items": [], "count": 0, "total": 0, "truncated": False},
            "disulfides": {"items": [], "count": 0, "total": 0, "truncated": False},
            "method": _method_block(),
            "limitation": _limitation_block(),
        }

    coords = np.array([a.xyz for a in atoms], dtype=float)
    hydrogens = _hydrogen_atoms(atoms)
    has_explicit_h = bool(hydrogens)

    hbonds: list[dict[str, Any]] = []
    salt_bridges: list[dict[str, Any]] = []
    hydrophobic: list[dict[str, Any]] = []
    disulfides: list[dict[str, Any]] = []
    counts = {"hbonds": 0, "salt_bridges": 0, "hydrophobic": 0, "disulfides": 0}

    # Largest cutoff drives one pass; each type filters from the shared pair set.
    max_cutoff = max(HBOND_MAX_DISTANCE, SALT_BRIDGE_MAX_DISTANCE,
                     HYDROPHOBIC_MAX_DISTANCE, DISULFIDE_MAX_DISTANCE)

    for i, j, dist in _neighbour_pairs(coords, max_cutoff):
        a, b = atoms[i], atoms[j]
        if a.chain == b.chain and a.res_seq == b.res_seq:
            continue

        # Disulfide bridges: covalent SG-SG, kept separate from non-covalent lists.
        if (a.res_name == "CYS" and b.res_name == "CYS"
                and a.element == "S" and b.element == "S"
                and dist <= DISULFIDE_MAX_DISTANCE):
            counts["disulfides"] += 1
            disulfides.append({
                "protein_residue": a.res_name,
                "protein_residue_seq": a.res_seq,
                "protein_chain": a.chain,
                "protein_atom": a.name,
                "partner_residue": b.res_name,
                "partner_residue_seq": b.res_seq,
                "partner_chain": b.chain,
                "partner_atom": b.name,
                "distance": round(dist, 3),
            })
            continue

        if _is_adjacent(a, b):
            continue

        # Hydrogen bonds: heavy-atom donor/acceptor within cutoff.
        if (a.element in DONOR_ACCEPTOR_ELEMENTS and b.element in DONOR_ACCEPTOR_ELEMENTS
                and dist <= HBOND_MAX_DISTANCE
                and _bond_angle_ok(a, b, dist, hydrogens)
                and _bond_angle_ok(b, a, dist, hydrogens)):
            counts["hbonds"] += 1
            hbonds.append({
                "donor": a.label, "donor_atom": a.name, "donor_chain": a.chain,
                "donor_residue_seq": a.res_seq,
                "acceptor": b.label, "acceptor_atom": b.name, "acceptor_chain": b.chain,
                "acceptor_residue_seq": b.res_seq,
                "distance": round(dist, 3),
                "geometry": "heavy_atom_distance_only" if not has_explicit_h
                            else "donor_h_acceptor_angle",
            })

        # Salt bridges: cationic side-chain N to anionic side-chain O.
        cation, anion = None, None
        if a.res_name in CATIONIC_RES and b.res_name in ANIONIC_RES:
            cation, anion = a, b
        elif b.res_name in CATIONIC_RES and a.res_name in ANIONIC_RES:
            cation, anion = b, a
        if cation is not None and anion is not None:
            if (cation.name in CATIONIC_NITROGENS.get(cation.res_name, ())
                    and anion.name in ANIONIC_OXYGENS.get(anion.res_name, ())
                    and dist <= SALT_BRIDGE_MAX_DISTANCE):
                counts["salt_bridges"] += 1
                salt_bridges.append({
                    "donor": cation.label, "donor_atom": cation.name,
                    "donor_chain": cation.chain, "donor_residue_seq": cation.res_seq,
                    "acceptor": anion.label, "acceptor_atom": anion.name,
                    "acceptor_chain": anion.chain, "acceptor_residue_seq": anion.res_seq,
                    "distance": round(dist, 3),
                    "charge_pair": f"{cation.res_name}+ / {anion.res_name}-",
                })

        # Hydrophobic core packing: apolar side-chain C/S across apolar residues.
        if (a.res_name in HYDROPHOBIC_RES and b.res_name in HYDROPHOBIC_RES
                and a.element in HYDROPHOBIC_ELEMENTS and b.element in HYDROPHOBIC_ELEMENTS
                and dist <= HYDROPHOBIC_MAX_DISTANCE):
            counts["hydrophobic"] += 1
            hydrophobic.append({
                "donor": a.label, "donor_atom": a.name, "donor_chain": a.chain,
                "donor_residue_seq": a.res_seq,
                "acceptor": b.label, "acceptor_atom": b.name,
                "acceptor_chain": b.chain,
                "acceptor_residue_seq": b.res_seq,
                "distance": round(dist, 3),
            })

    return {
        "hbonds": _collect("hydrogen-bond", hbonds, counts["hbonds"]),
        "salt_bridges": _collect("salt-bridge", salt_bridges, counts["salt_bridges"]),
        "hydrophobic": _collect("hydrophobic", hydrophobic, counts["hydrophobic"]),
        "disulfides": _collect("disulfide", disulfides, counts["disulfides"]),
        "method": _method_block(has_explicit_h),
        "limitation": _limitation_block(),
    }


def _method_block(explicit_hydrogens: bool | None = None) -> dict[str, Any]:
    return {
        "name": "BioNexus geometric intramolecular contacts",
        "kind": "intramolecular",
        "explicit_hydrogens": explicit_hydrogens,
        "criteria": {
            "hydrogen_bond": {
                "max_distance_angstrom": HBOND_MAX_DISTANCE,
                "min_dh_acceptor_angle_degrees": HBOND_MIN_ANGLE,
                "note": "angle test applies only when the structure carries explicit hydrogens",
            },
            "salt_bridge": {
                "max_distance_angstrom": SALT_BRIDGE_MAX_DISTANCE,
                "pairs": "LYS/ARG side-chain N to ASP/GLU side-chain O",
            },
            "hydrophobic": {
                "max_distance_angstrom": HYDROPHOBIC_MAX_DISTANCE,
                "residue_set": sorted(HYDROPHOBIC_RES),
                "elements": sorted(HYDROPHOBIC_ELEMENTS),
            },
            "disulfide": {
                "max_distance_angstrom": DISULFIDE_MAX_DISTANCE,
                "criterion": "CYS SG-SG",
            },
        },
        "excludes": "same and adjacent sequence positions within a chain (covalent neighbours)",
    }


def _limitation_block() -> str:
    return (
        "Geometric contacts only. Protonation states, explicit solvent, water bridges, "
        "and energetics are not modelled, so these counts are contact detections and "
        "not binding or stability energies."
    )
