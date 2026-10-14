"""Source-backed preparation for the simple GEO accession-to-figures workflow."""
import re
from .geo_counts import GeoCountsError

GROUP_KEYS = ('condition', 'disease state', 'disease', 'diagnosis', 'treatment', 'group', 'genotype', 'phenotype')
UNIT_KEYS = ('experimental unit', 'biological unit', 'subject id', 'subject_id', 'subject', 'patient id', 'patient_id', 'patient', 'donor id', 'donor_id', 'donor', 'animal id', 'animal', 'individual id')
TECHNICAL = re.compile(r'(^|[ _-])(batch|run|lane|plate|operator|site|processing[ _-]?day|extraction[ _-]?batch|kit[ _-]?lot|flow[ _-]?cell)([ _-]|$)', re.I)
RAW = re.compile(r'\b(?:raw|unnormalized|un-normalized)\s+(?:gene\s+|read\s+|integer\s+)?counts?\b|\bfeaturecounts\b|\bhtseq[ -]count\b', re.I)


def prepare(series, matrix, filename, source_url, group_key=None):
    samples = {s['accession']: s for s in series['samples']}
    identities = matrix['matched_samples']
    if any(gsm not in samples for gsm in identities) or len(set(identities)) != len(identities):
        raise GeoCountsError('GEO does not identify every count sample uniquely. Choose a matrix with sample identifiers matching this study; BioNexus will not guess or combine columns.')
    selected = [samples[gsm] for gsm in identities]
    methods = series.get('processing_methods', [])
    evidence = [line for line in methods if RAW.search(line)]
    # A deposited file explicitly named raw counts is itself a source statement,
    # distinct from merely seeing integer values in an arbitrary matrix.
    if re.search(r'(?:^|[._/-])raw[._ -]*(?:gene[._ -]*)?counts?(?:[._/-]|$)', filename, re.I):
        evidence.append('GEO deposited supplement explicitly labelled raw counts: ' + filename)
    if not evidence:
        raise GeoCountsError('This file contains integers, but GEO does not describe it as raw counts. Choose a supplement labelled raw counts or use the advanced source review. Normalized values cannot be converted back into original counts.')
    characteristics = [s.get('characteristics', {}) for s in selected]
    keys = list(dict.fromkeys([*GROUP_KEYS, *sorted({k for row in characteristics for k in row})]))
    choices = []
    seen = set()
    for key in keys:
        if TECHNICAL.search(key) or key in UNIT_KEYS:
            continue
        values = [row.get(key, '').strip() for row in characteristics]
        levels = sorted(set(values), key=str.casefold)
        if len(levels) == 2 and all(values) and min(values.count(v) for v in levels) >= 2 and tuple(values) not in seen:
            seen.add(tuple(values)); choices.append({'key': key, 'levels': levels, 'values': values})
    if not choices:
        # Replicate suffixes are removed only from complete matched GEO titles.
        values = [re.sub(r'(?:[ _.-]+(?:rep(?:licate)?[ _.-]*)?\d+)$', '', s['title'], flags=re.I).strip() for s in selected]
        levels = sorted(set(values), key=str.casefold)
        if len(levels) == 2 and all(values) and min(values.count(v) for v in levels) >= 2:
            choices.append({'key': 'sample title', 'levels': levels, 'values': values})
    if not choices:
        raise GeoCountsError('GEO does not describe a clear replicated two-group comparison for this matrix. Use advanced analysis to choose the study design; no sample groups have been guessed.')
    preferred = [c for c in choices if c['key'] in GROUP_KEYS]
    automatic = preferred[0] if len(preferred) == 1 else choices[0] if len(choices) == 1 else None
    choice = next((c for c in choices if c['key'] == group_key), None) if group_key else automatic
    if group_key and not choice:
        raise GeoCountsError('The chosen comparison is no longer present in the GEO metadata. Load the study again.')
    if not choice:
        return {'status': 'choose_comparison', 'comparisons': [{k: c[k] for k in ('key', 'levels')} for c in choices]}
    levels = choice['levels']
    controls = [v for v in levels if re.search(r'\b(control|healthy|normal|untreated|vehicle|wild[ -]?type|wt)\b', v, re.I)]
    reference = controls[0] if len(controls) == 1 else levels[0]
    test = next(v for v in levels if v != reference)
    unit_key = next((k for k in UNIT_KEYS if all(row.get(k, '').strip() for row in characteristics)), None)
    units = [row[unit_key].strip() for row in characteristics] if unit_key else identities
    if not unit_key and re.search(r'\b(paired|repeated|technical replicates|multiple samples per|same (?:patient|donor|animal))\b', series.get('design', ''), re.I):
        raise GeoCountsError('This study describes paired or repeated samples but does not identify their biological units. Use advanced analysis to supply the subject information.')
    if any(sum(unit == u and group == g for unit, group in zip(units, choice['values'])) > 1 for u, g in zip(units, choice['values'])):
        raise GeoCountsError('This comparison contains repeated measurements within a group. Advanced analysis needs an appropriate repeated-measurement design.')
    covariates = []
    rows = [{'sample': gsm, 'condition': group, 'experimental_unit': unit} for gsm, group, unit in zip(identities, choice['values'], units)]
    if len(set(units)) < len(units):
        covariates.append('experimental_unit')
    for index, key in enumerate(sorted({k for row in characteristics for k in row if TECHNICAL.search(k)})):
        values = [row.get(key, '').strip() for row in characteristics]
        if len(set(values)) <= 1:
            continue
        if not all(values):
            raise GeoCountsError(f'GEO is missing {key} for some samples. Use advanced analysis to review the missing batch information.')
        name = f'batch_{index + 1}'
        covariates.append(name)
        for row, value in zip(rows, values):
            row[name] = 'level:' + value
    return {'status': 'ready', 'accession': series['accession'], 'filename': filename, 'source_sha256': matrix['sha256'],
            'source_record_sha256': series['source_record_sha256'], 'genes': matrix['genes'], 'samples': len(rows),
            'reference_level': reference, 'test_level': test, 'group_key': choice['key'],
            'groups': [{'name': v, 'samples': choice['values'].count(v)} for v in (reference, test)],
            'covariates': covariates, 'metadata': rows,
            'organism': 'human' if set(series.get('organisms', [])) == {'Homo sapiens'} else 'mouse' if set(series.get('organisms', [])) == {'Mus musculus'} else 'auto',
            'source': {'classification': 'deposited_raw_counts', 'classification_basis': 'GEO_source_statement',
                       'evidence': evidence, 'processing_methods': methods, 'source_url': source_url,
                       'annotation_status': 'see_source_methods', 'independently_verified': False,
                       'experimental_unit_basis': unit_key or 'distinct deposited GEO samples; biological independence not independently verified',
                       'original_columns': matrix['columns'], 'mapped_samples': identities}}
