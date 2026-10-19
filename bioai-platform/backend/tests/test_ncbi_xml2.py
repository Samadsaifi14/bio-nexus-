"""Wire compatibility against real BLAST+ output, not invented hit records."""
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from app.integrations.ncbi.parser import parse_blast_xml

FIXTURES = Path(__file__).parent / 'fixtures' / 'blast_xml2'


def test_native_xml2_preserves_legacy_hit_and_alignment_contract():
    legacy = parse_blast_xml((FIXTURES / 'hbb-legacy.xml').read_text())
    modern = parse_blast_xml((FIXTURES / 'hbb-xml2.xml').read_text())
    assert 'error' not in modern
    assert modern == legacy
    assert modern['count'] == 3
    assert modern['query_length'] == 147
    assert modern['hits'][0]['identity_pct'] == 100.0
    assert modern['hits'][0]['query_alignment'].startswith('MVHLTPEEKS')


def test_xml2_preamble_without_xml_declaration():
    raw = (FIXTURES / 'hbb-xml2.xml').read_text().split('?>', 1)[1]
    assert parse_blast_xml('Status=READY\n' + raw)['count'] == 3


def test_xml2_completed_search_without_hits():
    root = ET.fromstring((FIXTURES / 'hbb-xml2.xml').read_text())
    root.find('.//{*}Search/{*}hits').clear()
    result = parse_blast_xml(ET.tostring(root, encoding='unicode'))
    assert 'error' not in result
    assert result['query_length'] == 147
    assert result['hits'] == []


@pytest.mark.parametrize('body', ['<html>Service unavailable</html>',
    '<BlastXML2 xmlns="http://www.ncbi.nlm.nih.gov"/>'])
def test_non_result_never_becomes_completed_no_hit(body):
    assert parse_blast_xml(body)['error']


def test_xml2_invalid_numeric_field_is_explicit_error():
    raw = (FIXTURES / 'hbb-xml2.xml').read_text().replace('<identity>147</identity>', '<identity>invalid</identity>', 1)
    assert 'invalid numeric field' in parse_blast_xml(raw)['error']
