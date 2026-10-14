import asyncio
import hashlib
import pytest
from fastapi import HTTPException
from app.tools.primer_binding import primer_binding_map
from app.tools.sequence_utilities import SequenceUtilitiesError
from app.routers.seq_tools import PrimerBindingRequest, primer_binding_endpoint
from app.tools.annotated_sequence import export_genbank
from Bio import SeqIO
from io import StringIO


def test_linear_product_and_reverse_primer_direction():
    template = 'AACCGGGGTTAA'
    r = primer_binding_map(template, 'AACC', 'TTAA')
    p = next(p for p in r['products'] if p['plus_primer'] == 'forward')
    assert (p['start'], p['end'], p['length']) == (1, 12, 12)
    assert p['sha256'] == hashlib.sha256(template.encode()).hexdigest()
    minus = next(s for s in r['sites'] if s['primer'] == 'reverse' and s['strand'] == -1)
    assert minus['three_prime_position'] == 9


def test_swapped_primer_labels_preserve_physical_product():
    a = primer_binding_map('AACCGGGGTTAA', 'AACC', 'TTAA')['products']
    b = primer_binding_map('AACCGGGGTTAA', 'TTAA', 'AACC')['products']
    assert [(p['start'], p['end'], p['sha256']) for p in a] == [(p['start'], p['end'], p['sha256']) for p in b]


def test_nonpalindromic_reverse_complement_and_three_prime_position():
    r = primer_binding_map('AACCGGGGGTCA', 'AACC', 'TGAC')
    assert r['sites'] == [
        {'primer': 'forward', 'strand': 1, 'start': 1, 'end': 4, 'spans_origin': False, 'three_prime_position': 4},
        {'primer': 'reverse', 'strand': -1, 'start': 9, 'end': 12, 'spans_origin': False, 'three_prime_position': 9},
    ]
    assert r['products'][0]['length'] == 12


def test_circular_product_crosses_origin_and_rotation_preserves_digest():
    seq = 'GGGGTTAAAACC'
    r = primer_binding_map(seq, 'AACC', 'TTAA', True)
    p = next(p for p in r['products'] if p['plus_primer'] == 'forward')
    assert (p['start'], p['end'], p['length'], p['spans_origin']) == (9, 8, 12, True)
    assert p['sha256'] == hashlib.sha256(b'AACCGGGGTTAA').hexdigest()
    for offset in range(len(seq)):
        rotated = seq[offset:] + seq[:offset]
        q = next(p for p in primer_binding_map(rotated, 'AACC', 'TTAA', True)['products'] if p['plus_primer'] == 'forward')
        assert q['sha256'] == p['sha256']
        assert q['length'] == p['length']
    assert not primer_binding_map(seq, 'AACC', 'TTAA')['products']


def test_origin_spanning_binding_has_correct_three_prime_end():
    r = primer_binding_map('CCGGGGTTAAAA', 'AACC', 'TTAA', True)
    plus = next(s for s in r['sites'] if s['primer'] == 'forward' and s['strand'] == 1)
    assert (plus['start'], plus['end'], plus['three_prime_position']) == (11, 2, 2)
    assert plus['spans_origin']
    features = [{'label': s['primer'], 'start': s['start'], 'end': s['end'], 'strand': s['strand'], 'type': 'primer_bind'} for s in r['sites']]
    exported = export_genbank('CCGGGGTTAAAA', 'primer_map', True, features, [])
    record = SeqIO.read(StringIO(exported['genbank']), 'genbank')
    for feature, site in zip(record.features, r['sites']):
        assert str(feature.extract(record.seq)) == r['primers'][site['primer']]


def test_product_size_bounds_no_match_and_overlap():
    assert not primer_binding_map('AACCGGGGTTAA', 'AACC', 'TTAA', max_product=11)['products']
    assert not primer_binding_map('AACCGGGGTTAA', 'AACC', 'TTAA', min_product=13)['products']
    assert primer_binding_map('AACCGGGGTTAA', 'CCCC', 'CCCC')['diagnostics']
    assert not primer_binding_map('AACCAA', 'AACC', 'TTGG')['products']


@pytest.mark.parametrize('seq,fwd,rev', [('AACNGGGGTTAA','AACC','TTAA'), ('AACCGGGGTTAA','AACN','TTAA'), ('AACCGGGGTTAA','AAC','TTAA'), ('AACC','AACCG','TTAA'), ('','AACC','TTAA')])
def test_invalid_and_ambiguous_inputs_rejected(seq, fwd, rev):
    with pytest.raises(SequenceUtilitiesError):
        primer_binding_map(seq, fwd, rev)


def test_repetitive_input_fails_instead_of_silent_truncation():
    with pytest.raises(SequenceUtilitiesError, match='200 exact'):
        primer_binding_map('A' * 300, 'AAAA', 'TTTT')
    with pytest.raises(SequenceUtilitiesError, match='100 candidate'):
        primer_binding_map('AAAACCCC' * 11, 'AAAA', 'GGGG', True)


def test_fasta_normalization_and_scientific_contract():
    r = asyncio.run(primer_binding_endpoint(PrimerBindingRequest(sequence='>template\naaccggggttaa', forward='AACC', reverse='TTAA')))
    assert r['results']['template_sha256'] == hashlib.sha256(b'AACCGGGGTTAA').hexdigest()
    assert r['validation']['exact_match_only'] is True
    assert r['validation']['genome_specificity_validated'] is False
    with pytest.raises(HTTPException) as exc:
        asyncio.run(primer_binding_endpoint(PrimerBindingRequest(sequence='AACCGGGGTTAA', forward='AACC', reverse='TTAA', min_product=20, max_product=10)))
    assert exc.value.status_code == 400
