"""Restore deposited ligand chemistry from the official Chemical Component Dictionary.

Only bond orders/charges come from the dictionary. Every heavy-atom coordinate
must be present under its exact CCD atom name in the selected deposited residue.
"""
from io import StringIO
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from rdkit import Chem


def deposited_ligand(ccd_text: str, pdb_lines: list[str]):
    data = MMCIF2Dict(StringIO(ccd_text))
    names = data['_chem_comp_atom.atom_id']
    elements = data['_chem_comp_atom.type_symbol']
    charges = data['_chem_comp_atom.charge']
    heavy = {name: element for name, element in zip(names, elements) if element != 'H'}
    positions = {}
    for line in pdb_lines:
        element = line[76:78].strip()
        if element == 'H':
            continue
        name = line[12:16].strip()
        if name in positions or name not in heavy or element.upper() != heavy[name].upper():
            raise ValueError('Deposited ligand atom identities differ from CCD')
        positions[name] = tuple(float(line[i:i + 8]) for i in (30, 38, 46))
    if positions.keys() != heavy.keys():
        raise ValueError('Deposited ligand is missing CCD heavy atoms')
    graph = Chem.RWMol()
    indices = {}
    for name, element, charge in zip(names, elements, charges):
        if element == 'H':
            continue
        atom = Chem.Atom(element.title())
        atom.SetFormalCharge(int(charge))
        atom.SetNoImplicit(True)
        indices[name] = graph.AddAtom(atom)
    hydrogen_counts = {name: 0 for name in heavy}
    orders = {'SING': Chem.BondType.SINGLE, 'DOUB': Chem.BondType.DOUBLE,
              'TRIP': Chem.BondType.TRIPLE, 'AROM': Chem.BondType.AROMATIC}
    for a, b, order in zip(data['_chem_comp_bond.atom_id_1'],
                           data['_chem_comp_bond.atom_id_2'], data['_chem_comp_bond.value_order']):
        if a in indices and b in indices:
            graph.AddBond(indices[a], indices[b], orders[order])
        elif a in indices:
            hydrogen_counts[a] += 1
        elif b in indices:
            hydrogen_counts[b] += 1
    for name, count in hydrogen_counts.items():
        graph.GetAtomWithIdx(indices[name]).SetNumExplicitHs(count)
    mol = graph.GetMol()
    Chem.SanitizeMol(mol)
    conf = Chem.Conformer(len(indices))
    for name, index in indices.items():
        conf.SetAtomPosition(index, positions[name])
    mol.AddConformer(conf)
    Chem.AssignStereochemistryFrom3D(mol)
    return mol
