"""Official CCD chemistry must not change deposited heavy-atom coordinates."""
from pathlib import Path
import pytest
from rdkit.Chem import rdMolDescriptors
from app.benchmarking.ligand_reference import deposited_ligand

FIXTURE = Path(__file__).parent / 'fixtures/ligand_ccd'


def test_pu2_official_graph_and_deposited_coordinates():
    lines = (FIXTURE / '1UYG_PU2.pdb').read_text().splitlines()
    mol = deposited_ligand((FIXTURE / 'PU2.cif').read_text(), lines)
    assert rdMolDescriptors.CalcMolFormula(mol) == 'C14H14FN5O2'
    assert mol.GetNumAtoms() == 22
    deposited = {tuple(float(line[i:i+8]) for i in (30, 38, 46)) for line in lines}
    assert {tuple(mol.GetConformer().GetAtomPosition(i)) for i in range(22)} == deposited


@pytest.mark.parametrize('damage', ['missing', 'duplicate', 'wrong_element'])
def test_incomplete_or_ambiguous_ligand_fails_closed(damage):
    lines = (FIXTURE / '1UYG_PU2.pdb').read_text().splitlines()
    if damage == 'missing':
        lines.pop()
    elif damage == 'duplicate':
        lines.append(lines[0])
    else:
        lines[0] = lines[0][:76] + ' O'
    with pytest.raises(ValueError, match='CCD'):
        deposited_ligand((FIXTURE / 'PU2.cif').read_text(), lines)
