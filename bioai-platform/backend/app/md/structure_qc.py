"""Input structure QC (MD Module 1) — pure-Python, no OpenMM required.

Validates the input PDB/mmCIF text and reports the things the MD design's
"Structure QC" module asks for: plausibility, residue naming, missing atoms
(OXT), alternate locations, crystallographic waters, metal ions and non-
standard residues. It is deliberately a *checker*, not a fixer — repair happens
in the protein-preparation stage with provenance recorded.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

_STANDARD_AA = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
}
_WATER = {"HOH", "H2O", "WAT", "TIP", "SOL"}
_METAL_IONS = {"ZN", "MG", "CA", "FE", "NA", "K", "MN", "CU", "CO", "NI", "CD", "HG", "LI", "SR"}


def structure_qc(pdb_text: str, pdb_id: str) -> dict:
    """Run Biopython structure QC and return a machine-auditable manifest.

    Never raises for structurally odd input: problems are *reported* as flags /
    residue lists so the orchestrator can decide whether to proceed.
    """
    from Bio.PDB import PDBParser

    if not pdb_text or "ATOM" not in pdb_text:
        return {
            "pdb_id": pdb_id,
            "parsed": False,
            "status": "UNPARSEABLE",
            "note": "No ATOM records found — not a valid protein structure.",
            "atom_count": 0,
            "residue_count": 0,
            "chain_count": 0,
            "protein_residues": 0,
        }

    try:
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure(pdb_id, io.StringIO(pdb_text))
        model = structure[0]
    except Exception as exc:
        return {
            "pdb_id": pdb_id,
            "parsed": False,
            "status": "UNPARSEABLE",
            "note": f"Biopython could not parse structure: {exc}",
            "atom_count": 0, "residue_count": 0, "chain_count": 0,
            "protein_residues": 0,
        }

    n_atoms = len(list(model.get_atoms()))
    chains = list(model.get_chains())
    n_chains = len(chains)

    residues = []
    saw_het = []
    waters = []
    metals = []
    missing_oxt = []
    altloc = set()
    by_name = {}
    for chain in chains:
        last = None
        for res in chain.get_residues():
            resname = (res.get_resname() or "").strip().upper()
            residues.append(resname)
            if res.is_disordered():
                altloc.add(res.id)
            if res.id[0] != " ":
                if resname in _WATER:
                    waters.append(f"{chain.id}{str(res.id[1])}{resname}")
                elif resname in _METAL_IONS:
                    metals.append(f"{chain.id}{str(res.id[1])}{resname}")
                else:
                    saw_het.append(f"{chain.id}{str(res.id[1])}{resname}")
                continue
            if resname in _STANDARD_AA:
                names = {a.get_name() for a in res.get_atoms()}
                # terminal OXT check only for C-terminal residues (last in chain)
                last = res
            else:
                saw_het.append(f"{chain.id}{str(res.id[1])}{resname}")
        # terminal residue of each chain: missing OXT?
        if last is not None:
            names = {a.get_name() for a in last.get_atoms()}
            if "OXT" not in names:
                missing_oxt.append(f"{last.get_parent().id}{str(last.id[1])}{last.get_resname().strip().upper()}")

    protein_residues = [r for r in residues if r in _STANDARD_AA]
    non_standard = sorted(set(saw_het))
    has_metal = bool(metals)

    issues = []
    if missing_oxt:
        issues.append(f"{len(missing_oxt)} C-terminal residue(s) missing OXT")
    if non_standard:
        issues.append(f"{len(non_standard)} non-standard residue(s): {', '.join(non_standard[:8])}")
    if waters:
        issues.append(f"{len(waters)} crystallographic water(s) present")
    if metals:
        issues.append(f"{len(metals)} metal ion(s) present: {', '.join(metals[:6])}")
    if altloc:
        issues.append(f"{len(altloc)} alternate-location residue(s) present")

    return {
        "pdb_id": pdb_id,
        "parsed": True,
        "status": "OK" if not non_standard else "NON_STANDARD_RESIDUES",
        "atom_count": n_atoms,
        "residue_count": len(residues),
        "chain_count": n_chains,
        "protein_residues": len(protein_residues),
        "nonstandard": non_standard,
        "nonstandard_count": len(non_standard),
        "waters": waters,
        "water_count": len(waters),
        "metals": metals,
        "metal_present": has_metal,
        "missing_oxt": missing_oxt,
        "missing_oxt_count": len(missing_oxt),
        "altloc_count": len(altloc),
        "issues": issues,
    }
