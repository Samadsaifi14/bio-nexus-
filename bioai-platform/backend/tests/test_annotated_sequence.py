from io import StringIO
import pytest
from Bio import SeqIO
from app.tools.annotated_sequence import export_genbank
from app.tools.sequence_utilities import SequenceUtilitiesError


def annotation(start, end, strand=1):
    return {'label': 'origin', 'start': start, 'end': end, 'strand': strand, 'type': 'misc_feature'}


def test_roundtrip():
    result = export_genbank('GAATTCAAAA', 'plasmid', True, [annotation(8, 3)], ['EcoRI'])
    record = SeqIO.read(StringIO(result['genbank']), 'genbank')
    assert str(record.seq) == 'GAATTCAAAA'
    assert record.annotations['topology'] == 'circular'
    assert len(record.features) == 2
    assert str(record.features[0].extract(record.seq)) == 'AAAGAA'
    assert record.features[1].qualifiers['label'] == ['EcoRI']


def test_reverse_origin():
    result = export_genbank('GAATTCAAAA', 'plasmid', True, [annotation(8, 3, -1)], [])
    record = SeqIO.read(StringIO(result['genbank']), 'genbank')
    assert str(record.features[0].extract(record.seq)) == 'TTCTTT'
    assert result['features'][0]['sequence'] == 'TTCTTT'


@pytest.mark.parametrize('feature,circular', [(annotation(8, 3), False), (annotation(1, 11), True), (annotation(0, 3), True)])
def test_invalid_coordinates(feature, circular):
    with pytest.raises(SequenceUtilitiesError):
        export_genbank('GAATTCAAAA', 'plasmid', circular, [feature], [])


def test_label_and_determinism():
    bad = annotation(1, 3); bad['label'] = 'bad\nORIGIN'
    with pytest.raises(SequenceUtilitiesError):
        export_genbank('GAATTC', 'plasmid', False, [bad], [])
    assert export_genbank('GAATTC', 'plasmid', False, [], []) == export_genbank('GAATTC', 'plasmid', False, [], [])


@pytest.mark.asyncio
async def test_endpoint():
    from app.routers.seq_tools import AnnotatedSequenceRequest, annotated_genbank_endpoint
    result = await annotated_genbank_endpoint(AnnotatedSequenceRequest(sequence='GAATTC'))
    assert result['validation']['biological_annotations_validated'] is False
    assert result['results']['filename'] == 'BioNexus_DNA.gb'
