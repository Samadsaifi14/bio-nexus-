import hashlib
import pytest
from app.tools.alignment_trim import trim_alignment


def test_default_preserves_ungapped_residues_and_maps():
    source = '>a description\na--ct\n>b\na--gt\n'
    result = trim_alignment(source, 'dna')
    assert result['trimmed_fasta'] == '>a description\nACT\n>b\nAGT\n'
    assert result['mask']['kept_columns'] == [1, 4, 5]
    assert result['mask']['dropped_columns'] == [2, 3]
    assert result['mask']['residues_removed'] == 0
    assert result['mask']['input_sha256'] == hashlib.sha256(source.encode()).hexdigest()
    assert result['mask']['output_sha256'] == hashlib.sha256(result['trimmed_fasta'].encode()).hexdigest()


def test_aggressive_boundary_and_residue_deletion():
    source = '>a\nA-CT\n>b\nAG-T\n'
    assert trim_alignment(source, 'dna', 'any_gap')['trimmed_fasta'] == '>a\nAT\n>b\nAT\n'
    result = trim_alignment(source, 'dna', 'gap_percent', 50)
    assert result['mask']['dropped_columns'] == [2, 3]
    assert result['mask']['residues_removed'] == 2
    assert trim_alignment(source, 'dna', 'gap_percent', 50.1)['mask']['dropped_columns'] == []


@pytest.mark.parametrize('source,molecule', [('ACGT', 'dna'), ('>a\nAC\n>a desc\nAC', 'dna'), ('>a\nAC\n>b\nA', 'dna'), ('>a\nAN\n>b\nAC', 'dna'), ('>a\nAT\n>b\nAU', 'rna'), ('>a\nAX\n>b\nAA', 'protein'), ('>a\nAA', 'dna'), ('>\nAC\n>b\nAC', 'dna'), ('>   \nAC\n>b\nAC', 'dna'), ('>a\n--\n>b\n--', 'dna')])
def test_invalid(source, molecule):
    with pytest.raises(ValueError):
        trim_alignment(source, molecule)


@pytest.mark.parametrize('threshold', [0, -1, 101, float('nan'), float('inf')])
def test_threshold_validation(threshold):
    with pytest.raises(ValueError):
        trim_alignment('>a\nAC\n>b\nAC', 'dna', 'gap_percent', threshold)


def test_rna_and_protein():
    assert trim_alignment('>a\nAU-\n>b\nAC-', 'rna')['mask']['kept_columns'] == [1, 2]
    assert trim_alignment('>a\nEF-\n>b\nWY-', 'protein')['mask']['kept_columns'] == [1, 2]


def test_all_columns_dropped_aggressive():
    with pytest.raises(ValueError, match='every column'):
        trim_alignment('>a\n-A\n>b\nA-', 'dna', 'any_gap')


def test_endpoint_envelope_and_validation():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.seq_tools import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.post('/api/seq-tools/alignment-trim', json={'fasta': '>a\nAC-\n>b\nAT-', 'molecule': 'dna'})
    assert response.status_code == 200
    data = response.json()
    assert data['results']['mask']['kept_columns'] == [1, 2]
    assert data['validation']['realignment_performed'] is False
    assert client.post('/api/seq-tools/alignment-trim', json={'fasta': '>a\nAN\n>b\nAC', 'molecule': 'dna'}).status_code == 400
    assert client.post('/api/seq-tools/alignment-trim', json={'fasta': '>a\nAC\n>b\nAC', 'gap_percent': 0}).status_code == 422
