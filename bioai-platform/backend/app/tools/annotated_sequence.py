"""Portable GenBank exchange for explicitly supplied DNA annotations.

Features use 1-based inclusive coordinates; start > end spans a circular origin.
No biological annotation is inferred from user labels.
"""
from io import StringIO
import re
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, SimpleLocation, CompoundLocation
from app.tools.sequence_utilities import clean_sequence, SequenceUtilitiesError
from app.tools.restriction_map import restriction_map


def export_genbank(sequence, name, circular, features, enzymes):
    sequence = clean_sequence(sequence, 'dna')
    if len(sequence) > 200000:
        raise SequenceUtilitiesError('Annotated DNA is limited to 200,000 bases')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,15}', name):
        raise SequenceUtilitiesError('Record name must start with a letter and contain at most 16 letters, digits, dots, hyphens or underscores')
    record = SeqRecord(Seq(sequence), id=name, name=name, description='BioNexus user-annotated DNA; annotations are not experimentally validated')
    record.annotations = {'molecule_type': 'DNA', 'topology': 'circular' if circular else 'linear', 'data_file_division': 'SYN', 'date': '01-JAN-1980'}
    normalized = []
    if len(features) > 200:
        raise SequenceUtilitiesError('At most 200 annotations are supported')
    for feature in features:
        start, end, strand = feature['start'], feature['end'], feature['strand']
        label, kind = feature['label'], feature['type']
        if not (1 <= start <= len(sequence) and 1 <= end <= len(sequence)):
            raise SequenceUtilitiesError('Annotation coordinates must be inside the sequence')
        if strand not in (-1, 1) or kind not in ('misc_feature', 'gene', 'promoter', 'rep_origin', 'primer_bind'):
            raise SequenceUtilitiesError('Unsupported annotation strand or type')
        if not label.strip() or len(label) > 100 or any(ord(c) < 32 or c == '"' for c in label):
            raise SequenceUtilitiesError('Annotation labels require 1–100 printable characters without double quotes')
        if start > end:
            if not circular:
                raise SequenceUtilitiesError('Origin-spanning annotations require circular DNA')
            parts = [SimpleLocation(start - 1, len(sequence), strand=strand), SimpleLocation(0, end, strand=strand)]
            if strand == -1:
                parts.reverse()
            location = CompoundLocation(parts)
        else:
            location = SimpleLocation(start - 1, end, strand=strand)
        record.features.append(SeqFeature(location, type=kind, qualifiers={'label': [label], 'note': ['User-supplied annotation; not independently verified']}))
        normalized.append({**feature, 'length': len(location), 'sequence': str(location.extract(record.seq)), 'source': 'user supplied'})
    if enzymes:
        mapped = restriction_map(sequence, enzymes, circular)
        for site in mapped['sites']:
            start, end = site['start'], site['end']
            strand = 1 if site['strand'] == '+' else -1
            parts = [SimpleLocation(start - 1, len(sequence), strand=strand), SimpleLocation(0, end, strand=strand)] if site['spans_origin'] else None
            if parts and strand == -1:
                parts.reverse()
            location = CompoundLocation(parts) if parts else SimpleLocation(start - 1, end, strand=strand)
            record.features.append(SeqFeature(location, type='misc_feature', qualifiers={'label': [site['enzyme']], 'note': [f"Restriction recognition site; top cut boundary {site['top_cut_boundary']}; bottom cut boundary {site['bottom_cut_boundary']}; complete cut {site['complete_cut']}"]}))
    output = StringIO()
    SeqIO.write(record, output, 'genbank')
    return {'genbank': output.getvalue(), 'filename': name + '.gb', 'length': len(sequence), 'topology': record.annotations['topology'], 'features': normalized, 'exported_feature_count': len(record.features), 'coordinate_convention': '1-based inclusive; start > end crosses circular origin', 'limitations': 'User labels are unverified. Restriction sites are deterministic recognition matches. No cloning, expression or experimental validation is implied. GenBank date is a fixed placeholder for reproducible export.'}
