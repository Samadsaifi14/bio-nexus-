"""Strict bounded protein collections; validation never queues work."""
import re
from app.services.sequence_utils import detect_sequence_type


def validate_protein_collection(text: str) -> list[dict]:
    if len(text) > 110000 or not text.strip().startswith('>'):
        raise ValueError('Provide multi-FASTA input, at most 110 KB')
    records = []
    for block in text.strip().split('>')[1:]:
        lines = block.splitlines()
        header = lines[0].strip() if lines else ''
        identifier = header.split()[0] if header else ''
        if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', identifier):
            raise ValueError('Each FASTA identifier must contain 1–100 safe identifier characters')
        seq = ''.join(''.join(lines[1:]).split()).upper()
        if not 6 <= len(seq) <= 10000 or set(seq) - set('ACDEFGHIKLMNPQRSTVWY'):
            raise ValueError(f'{identifier}: require 6–10000 canonical amino acids without gaps or ambiguity')
        if detect_sequence_type(seq) != 'protein':
            raise ValueError(f'{identifier}: molecule type is nucleotide or ambiguous, not unambiguous protein')
        records.append({'identifier': identifier, 'sequence': seq})
    if not 1 <= len(records) <= 10:
        raise ValueError('A collection must contain 1–10 records')
    if len({r['identifier'] for r in records}) != len(records):
        raise ValueError('FASTA identifiers must be unique')
    return records
