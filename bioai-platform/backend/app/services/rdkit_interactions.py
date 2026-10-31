"""RDKit-backed, evidence-preserving protein-ligand interaction analysis.

This module intentionally fails closed when chemical perception or coordinate
mapping is not trustworthy. A missing classification is never converted to a
zero-contact claim.
"""
from __future__ import annotations

import math
from typing import Any

from rdkit import Chem, RDConfig
from rdkit.Chem import AllChem, ChemicalFeatures
from rdkit.Geometry import Point3D


_THRESHOLDS = {
    "hbond_distance_angstrom": 3.5,
    "hbond_angle_degrees": 120.0,
    "hydrophobic_distance_angstrom": 4.5,
    "salt_bridge_distance_angstrom": 4.0,
    "pi_centroid_distance_angstrom": 5.5,
    "pi_parallel_angle_degrees": 30.0,
    "pi_t_shaped_angle_min_degrees": 60.0,
    "pi_t_shaped_angle_max_degrees": 90.0,
}


def _feature_factory():
    path = f"{RDConfig.RDDataDir}/BaseFeatures.fdef"
    return ChemicalFeatures.BuildFeatureFactory(path)


def _normalize_pose_pdb(block: str) -> str:
    """Rebuild fixed-column PDB records from PDBQT while preserving atom order/coordinates."""
    rows = []
    for line in block.splitlines():
        if line[:6].strip() not in ("ATOM", "HETATM"):
            continue
        fields = line.split()
        if len(fields) < 9:
            continue
        try:
            serial = int(fields[1])
            atom_name = fields[2]
            x, y, z = (float(fields[i]) for i in (5, 6, 7))
            element = fields[-1].strip().upper()
        except (ValueError, IndexError):
            continue
        element = "".join(ch for ch in element if ch.isalpha())[:2].title()
        if not element:
            element = "".join(ch for ch in atom_name if ch.isalpha())[:1].title()
        atom_field = f" {atom_name:<3s}"[:4] if len(atom_name) < 4 else atom_name[:4]
        rows.append(
            f"ATOM  {serial:5d} {atom_field:4s} UNL A   1    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}{1.0:6.2f}{0.0:6.2f}          {element:>2s}  "
        )
    if not rows:
        raise ValueError("Could not recover ligand atom coordinates from PDB/PDBQT records")
    return "\\n".join(rows) + "\\nEND\\n"


def _pdb_mol(block: str, label: str):
    if not block or not any(line.startswith(("ATOM  ", "HETATM")) for line in block.splitlines()):
        raise ValueError(f"{label} structure contains no PDB atom records")
    try:
        mol = Chem.MolFromPDBBlock(block, sanitize=True, removeHs=False, proximityBonding=True)
    except Exception:
        mol = None
    if mol is None and label == "ligand":
        normalized = _normalize_pose_pdb(block)
        mol = Chem.MolFromPDBBlock(normalized, sanitize=True, removeHs=False, proximityBonding=True)
    if mol is None or mol.GetNumHeavyAtoms() == 0:
        raise ValueError(f"RDKit could not construct a chemically usable {label} molecule")
    return mol


def _protein_mol(block: str):
    """Parse protein residues independently to prevent false inter-residue proximity bonds.

    Reconnects sequential peptide C-N bonds after residue-level chemical perception.
    Any residue that cannot be perceived is explicitly recorded as excluded.
    """
    from collections import OrderedDict
    residues = OrderedDict()
    for line in block.splitlines():
        if line.startswith("ATOM  "):
            if len(line) > 16 and line[16] not in (" ", "A"):
                continue
            key = (line[21:22], line[22:26], line[26:27], line[17:20])
            residues.setdefault(key, []).append(line)
    parsed = []
    skipped = []
    for key, lines in residues.items():
        residue_block = "\\n".join(lines) + "\\nEND\\n"
        try:
            residue_mol = Chem.MolFromPDBBlock(
                residue_block, sanitize=True, removeHs=False, proximityBonding=True
            )
        except Exception:
            residue_mol = None
        if residue_mol is None or residue_mol.GetNumHeavyAtoms() == 0:
            skipped.append({"chain": key[0].strip(), "residue_number": key[1].strip(),
                            "residue_name": key[3].strip(), "reason": "RDKit residue sanitization failed"})
            continue
        parsed.append((key, residue_mol))
    if not parsed:
        raise ValueError("RDKit could not chemically perceive any protein residues")
    combined = parsed[0][1]
    residue_atom_indices = []
    for key, mol in parsed:
        if mol is not parsed[0][1]:
            offset = combined.GetNumAtoms()
            combined = Chem.CombineMols(combined, mol)
        else:
            offset = 0
        names = {}
        for atom in mol.GetAtoms():
            info = atom.GetPDBResidueInfo()
            if info:
                names[info.GetName().strip()] = atom.GetIdx() + offset
        residue_atom_indices.append((key, names))
    editable = Chem.RWMol(combined)
    peptide_bonds_added = 0
    for (left_key, left_atoms), (right_key, right_atoms) in zip(residue_atom_indices, residue_atom_indices[1:]):
        same_chain = left_key[0] == right_key[0]
        try:
            sequential = int(right_key[1]) == int(left_key[1]) + 1
        except ValueError:
            sequential = False
        if same_chain and sequential and "C" in left_atoms and "N" in right_atoms:
            c_idx, n_idx = left_atoms["C"], right_atoms["N"]
            p1 = combined.GetConformer().GetAtomPosition(c_idx)
            p2 = combined.GetConformer().GetAtomPosition(n_idx)
            distance = p1.Distance(p2)
            if 1.1 <= distance <= 1.8:
                editable.AddBond(c_idx, n_idx, Chem.BondType.SINGLE)
                peptide_bonds_added += 1
    protein = editable.GetMol()
    Chem.SanitizeMol(protein)
    protein.SetProp("_omvetra_skipped_residues", json.dumps(skipped))
    protein.SetProp("_omvetra_peptide_bonds_added", str(peptide_bonds_added))
    return protein


def _ligand_with_template(ligand_pdb: str, smiles: str):
    template = Chem.MolFromSmiles(smiles)
    if template is None:
        raise ValueError("Ligand SMILES could not be parsed by RDKit")
    pose = Chem.RemoveHs(_pdb_mol(ligand_pdb, "ligand"))
    if pose.GetNumHeavyAtoms() != template.GetNumHeavyAtoms():
        raise ValueError(
            "Ligand pose atom count does not match the submitted SMILES "
            f"({pose.GetNumHeavyAtoms()} vs {template.GetNumHeavyAtoms()}); refusing atom mapping"
        )
    try:
        mapped = AllChem.AssignBondOrdersFromTemplate(template, pose)
    except Exception as exc:
        raise ValueError(f"RDKit could not map ligand pose to submitted SMILES: {exc}") from exc
    if mapped is None or mapped.GetNumHeavyAtoms() != template.GetNumHeavyAtoms():
        raise ValueError("RDKit ligand bond-order assignment did not preserve the expected atom graph")
    return mapped


def _with_hydrogens(mol):
    if mol.GetNumConformers() == 0:
        raise ValueError("Structure has no coordinate conformer")
    return Chem.AddHs(mol, addCoords=True)


def _coords(mol, atom_id: int):
    p = mol.GetConformer().GetAtomPosition(atom_id)
    return (float(p.x), float(p.y), float(p.z))


def _distance(a, b):
    return math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))


def _angle(a, b, c):
    ba = tuple(x-y for x, y in zip(a, b))
    bc = tuple(x-y for x, y in zip(c, b))
    na = math.sqrt(sum(v*v for v in ba))
    nc = math.sqrt(sum(v*v for v in bc))
    if na < 1e-8 or nc < 1e-8:
        return 0.0
    cosine = max(-1.0, min(1.0, sum(x*y for x, y in zip(ba, bc))/(na*nc)))
    return math.degrees(math.acos(cosine))


def _atom_features(mol, factory):
    result = {name: set() for name in ("Donor", "Acceptor", "Hydrophobe", "PosIonizable", "NegIonizable")}
    for feature in factory.GetFeaturesForMol(mol):
        name = feature.GetFamily()
        if name not in result:
            continue
        for atom_id in feature.GetAtomIds():
            if mol.GetAtomWithIdx(atom_id).GetAtomicNum() > 1:
                result[name].add(atom_id)
    return result


def _residue(atom):
    info = atom.GetPDBResidueInfo()
    if info is None:
        return {"name": "UNK", "chain": "", "number": None, "atom": atom.GetSymbol()}
    return {
        "name": info.GetResidueName().strip(),
        "chain": info.GetChainId().strip(),
        "number": int(info.GetResidueNumber()),
        "atom": info.GetName().strip(),
    }


def _ring_geometry(mol, atom_ids):
    points = [_coords(mol, idx) for idx in atom_ids]
    if len(points) < 3:
        return None
    center = tuple(sum(p[i] for p in points)/len(points) for i in range(3))
    # Least-squares plane normal using RDKit's NumPy dependency.
    import numpy as np
    centered = np.asarray(points, dtype=float) - np.asarray(center)
    _, singular, vh = np.linalg.svd(centered, full_matrices=False)
    if len(singular) < 2 or singular[1] < 1e-6:
        return None
    normal = vh[-1]
    norm = float(np.linalg.norm(normal))
    if norm < 1e-9:
        return None
    return center, tuple(float(x/norm) for x in normal)


def _ring_interactions(protein, ligand, protein_features, ligand_features):
    rows = []
    protein_rings = [f.GetAtomIds() for f in _feature_factory().GetFeaturesForMol(protein)
                     if f.GetFamily() == "Aromatic" and len(f.GetAtomIds()) >= 5]
    ligand_rings = [f.GetAtomIds() for f in _feature_factory().GetFeaturesForMol(ligand)
                    if f.GetFamily() == "Aromatic" and len(f.GetAtomIds()) >= 5]
    for pids in protein_rings:
        pg = _ring_geometry(protein, pids)
        if pg is None:
            continue
        pc, pn = pg
        p_atom = protein.GetAtomWithIdx(int(pids[0]))
        pres = _residue(p_atom)
        for lids in ligand_rings:
            lg = _ring_geometry(ligand, lids)
            if lg is None:
                continue
            lc, ln = lg
            d = _distance(pc, lc)
            if d > _THRESHOLDS["pi_centroid_distance_angstrom"]:
                continue
            cosine = abs(sum(x*y for x, y in zip(pn, ln)))
            plane_angle = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
            # 0° normals = parallel planes; 90° normals = perpendicular planes.
            if plane_angle <= _THRESHOLDS["pi_parallel_angle_degrees"]:
                kind = "parallel"
            elif (_THRESHOLDS["pi_t_shaped_angle_min_degrees"] <= plane_angle
                  <= _THRESHOLDS["pi_t_shaped_angle_max_degrees"]):
                kind = "t_shaped"
            else:
                continue
            rows.append({
                "type": "pi_stacking", "protein_residue": pres["name"],
                "protein_residue_seq": pres["number"], "protein_chain": pres["chain"],
                "protein_ring_atom_indices": list(pids), "ligand_ring_atom_indices": list(lids),
                "protein_centroid": list(pc), "ligand_centroid": list(lc),
                "centroid_distance": round(d, 3), "ring_plane_angle": round(plane_angle, 2),
                "geometry": kind, "method": "RDKit aromatic ring features + least-squares plane geometry",
            })
    return rows


def calculate_interactions(protein_pdb: str, ligand_pdb: str, ligand_smiles: str) -> dict[str, Any]:
    """Return RDKit feature-based interaction evidence for one docked pose."""
    factory = _feature_factory()
    protein_raw = _protein_mol(protein_pdb)\n    protein_parse = {\n        "parser": "RDKit residue-wise perception with sequential peptide-bond reconstruction",\n        "residues_skipped": json.loads(protein_raw.GetProp("_omvetra_skipped_residues")),\n        "peptide_bonds_reconstructed": int(protein_raw.GetProp("_omvetra_peptide_bonds_added")),\n    }\n    protein = _with_hydrogens(protein_raw)
    ligand = _with_hydrogens(_ligand_with_template(ligand_pdb, ligand_smiles))
    pf = _atom_features(protein, factory)
    lf = _atom_features(ligand, factory)

    hbonds, hydrophobic, salt_bridges = [], [], []
    # Donor/acceptor features are chemical SMARTS classifications, not element-only rules.
    for donor_mol, donor_ids, acceptor_mol, acceptor_ids, direction in (
        (ligand, lf["Donor"], protein, pf["Acceptor"], "ligand_to_protein"),
        (protein, pf["Donor"], ligand, lf["Acceptor"], "protein_to_ligand"),
    ):
        for did in donor_ids:
            donor = donor_mol.GetAtomWithIdx(did)
            hydrogens = [n.GetIdx() for n in donor.GetNeighbors() if n.GetAtomicNum() == 1]
            if not hydrogens:
                continue
            dcoord = _coords(donor_mol, did)
            for aid in acceptor_ids:
                acoord = _coords(acceptor_mol, aid)
                distance = _distance(dcoord, acoord)
                if not 1.0 < distance <= _THRESHOLDS["hbond_distance_angstrom"]:
                    continue
                best_angle = max(_angle(_coords(donor_mol, hid), dcoord, acoord) for hid in hydrogens)
                if best_angle < _THRESHOLDS["hbond_angle_degrees"]:
                    continue
                da, aa = donor.GetPDBResidueInfo(), acceptor_mol.GetAtomWithIdx(aid).GetPDBResidueInfo()
                hbonds.append({
                    "type": "hbond", "direction": direction,
                    "donor_atom_index": did, "acceptor_atom_index": aid,
                    "donor_residue": _residue(donor), "acceptor_residue": _residue(acceptor_mol.GetAtomWithIdx(aid)),
                    "distance": round(distance, 3), "donor_h_acceptor_angle": round(best_angle, 2),
                    "method": "RDKit donor/acceptor chemical features + explicit-H geometry",
                })

    # Hydrophobic features are chemically classified by RDKit's BaseFeatures.
    for lid in lf["Hydrophobe"]:
        for pid in pf["Hydrophobe"]:
            distance = _distance(_coords(ligand, lid), _coords(protein, pid))
            if distance <= _THRESHOLDS["hydrophobic_distance_angstrom"]:
                hydrophobic.append({
                    "type": "hydrophobic", "ligand_atom_index": lid,
                    "protein_atom_index": pid, "protein_residue": _residue(protein.GetAtomWithIdx(pid)),
                    "distance": round(distance, 3),
                    "method": "RDKit Hydrophobe chemical features + heavy-atom distance",
                })

    # Formal charge features are required on BOTH partners.
    for positive_mol, positive_ids, negative_mol, negative_ids, label in (
        (ligand, lf["PosIonizable"], protein, pf["NegIonizable"], "ligand_positive_protein_negative"),
        (protein, pf["PosIonizable"], ligand, lf["NegIonizable"], "protein_positive_ligand_negative"),
    ):
        for pos in positive_ids:
            for neg in negative_ids:
                distance = _distance(_coords(positive_mol, pos), _coords(negative_mol, neg))
                if distance <= _THRESHOLDS["salt_bridge_distance_angstrom"]:
                    salt_bridges.append({
                        "type": "salt_bridge", "charge_pair": label,
                        "positive_atom_index": pos, "negative_atom_index": neg,
                        "positive_residue": _residue(positive_mol.GetAtomWithIdx(pos)),
                        "negative_residue": _residue(negative_mol.GetAtomWithIdx(neg)),
                        "distance": round(distance, 3),
                        "method": "RDKit PosIonizable/NegIonizable chemical features + distance",
                    })

    pi_stacking = _ring_interactions(protein, ligand, pf, lf)
    categories = {
        "hbonds": hbonds, "hydrophobic": hydrophobic,
        "pi_stacking": pi_stacking, "salt_bridges": salt_bridges,
    }
    return {
        **categories,
        "status": "COMPUTED",
        "engine": "RDKit",
        "engine_version": Chem.rdBase.rdkitVersion,
        "method": "RDKit BaseFeatures chemical perception with explicit-coordinate geometry",
        "thresholds": dict(_THRESHOLDS),
        "counts": {key: len(value) for key, value in categories.items()},
        "limitations": [
            "Interaction classifications depend on the supplied protonation/tautomer state and prepared coordinates.",
            "RDKit feature perception is a computational model, not experimental evidence of binding.",
            "Only the provided receptor atoms and docked pose are evaluated; omitted waters, ions, cofactors, and alternate conformations are not inferred.",\n            "Residues listed in protein_parse.residues_skipped were excluded from chemical feature perception; a DEGRADED status must not be interpreted as complete receptor coverage.",
            "Distances and angles are geometric screens, not interaction energies or binding-affinity measurements.",
        ],
    }
