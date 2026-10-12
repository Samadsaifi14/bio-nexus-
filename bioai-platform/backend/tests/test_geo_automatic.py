"""Regression controls for accession-to-figures without manual mapping forms."""
import asyncio
import copy
import csv
import io
import json
import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException
from app.rnaseq.geo_automatic import prepare
from app.rnaseq.geo_counts import GeoCountsError
from app.rnaseq import durable, expression
from app.routers import geo_search


def study():
    samples = [{'accession': f'GSM{i+1}', 'title': f'{"healthy" if i < 2 else "disease"} rep{i % 2+1}',
                'characteristics': {'condition': 'healthy' if i < 2 else 'disease'}} for i in range(4)]
    series = {'accession': 'GSE1', 'title': 'RNA-seq', 'design': 'Four biological samples', 'samples': samples,
              'source_record_sha256': 'metadata-hash', 'processing_methods': ['Gene reads counted with featureCounts against GENCODE v44'],
              'organisms': ['Homo sapiens'], 'files': [{'name': 'counts.tsv', 'scope': 'series', 'analysis_eligible': True}]}
    matrix = {'matched_samples': ['GSM3', 'GSM1', 'GSM4', 'GSM2'], 'columns': ['d1', 'h1', 'd2', 'h2'],
              'rows': [['gene1', 3, 1, 4, 2]], 'sha256': 'counts-hash', 'genes': 1}
    return series, matrix


def test_reordered_samples_prepared_without_manual_assignments():
    series, matrix = study()
    result = prepare(series, matrix, 'counts.tsv', 'https://ftp.ncbi.nlm.nih.gov/counts.tsv')
    assert result['reference_level'] == 'healthy'
    assert [r['condition'] for r in result['metadata']] == ['disease', 'healthy', 'disease', 'healthy']
    assert [r['sample'] for r in result['metadata']] == matrix['matched_samples']
    assert result['source']['classification_basis'] == 'GEO_source_statement'


@pytest.mark.parametrize('ids', [[None, 'GSM1', 'GSM4', 'GSM2'], ['GSM1', 'GSM1', 'GSM4', 'GSM2']])
def test_never_guesses_unresolved_or_duplicate_mapping(ids):
    s, m = study(); m['matched_samples'] = ids
    with pytest.raises(GeoCountsError, match='uniquely'):
        prepare(s, m, 'counts.tsv', 'source')


def test_integer_values_alone_do_not_classify_raw_counts():
    s, m = study(); s['processing_methods'] = ['Expression was normalized to TPM']
    with pytest.raises(GeoCountsError, match='integers'):
        prepare(s, m, 'matrix.tsv', 'source')
    r = prepare(s, m, 'GSE1_raw_counts.tsv', 'source')
    assert r['source']['evidence'][-1].startswith('GEO deposited')


def test_alternative_biological_comparisons_ask_one_choice():
    s, m = study()
    for i, sample in enumerate(s['samples']):
        sample['characteristics']['treatment'] = 'vehicle' if i % 2 == 0 else 'drug'
    r = prepare(s, m, 'counts.tsv', 'source')
    assert r['status'] == 'choose_comparison'
    assert {c['key'] for c in r['comparisons']} == {'condition', 'treatment'}
    assert prepare(s, m, 'counts.tsv', 'source', 'condition')['status'] == 'ready'


def test_paired_and_batch_metadata_are_modelled_as_categories():
    s, m = study()
    for i, sample in enumerate(s['samples']):
        sample['characteristics'].update({'subject id': str(i % 2), 'batch': str(i % 2)})
    r = prepare(s, m, 'counts.tsv', 'source')
    assert r['covariates'] == ['experimental_unit', 'batch_1']
    assert all(row['batch_1'].startswith('level:') for row in r['metadata'])


def test_repeated_samples_and_missing_batch_are_not_silently_ignored():
    s, m = study()
    for sample in s['samples']: sample['characteristics']['subject id'] = 'same'
    with pytest.raises(GeoCountsError, match='repeated measurements'):
        prepare(s, m, 'counts.tsv', 'source')
    s, m = study(); s['samples'][0]['characteristics']['batch'] = 'A'
    with pytest.raises(GeoCountsError, match='missing batch'):
        prepare(s, m, 'counts.tsv', 'source')


def test_complete_matched_titles_are_used_when_condition_is_absent():
    s, m = study()
    for sample in s['samples']: sample['characteristics'] = {}
    assert prepare(s, m, 'counts.tsv', 'source')['reference_level'] == 'healthy'
    s['design'] = 'paired samples from the same donor'
    with pytest.raises(GeoCountsError, match='biological units'):
        prepare(s, m, 'counts.tsv', 'source')


def fake_sources(monkeypatch):
    s, m = study()
    async def series(*args): return copy.deepcopy(s)
    async def matrix(*args): return copy.deepcopy(m), 'https://ftp.ncbi.nlm.nih.gov/counts.tsv'
    monkeypatch.setattr(geo_search, 'fetch_series', series)
    monkeypatch.setattr(geo_search, 'fetch_matrix', matrix)
    return s, m


@pytest.mark.parametrize('queue', [True, False])
def test_full_analysis_submission_and_direct_R_fallback(monkeypatch, queue):
    fake_sources(monkeypatch)
    monkeypatch.setattr(durable, 'readiness', lambda: {'available': queue})
    monkeypatch.setattr(geo_search, 'expression_readiness', lambda: {'available': True})
    captured = {}
    def enqueue(**kwargs):
        captured.update(kwargs, counts=kwargs['counts'].read_text(), metadata=kwargs['metadata'].read_text())
        return {'job_id': 'job'}
    def execute(**kwargs):
        captured.update(kwargs, counts=kwargs['counts_path'].read_text(), metadata=kwargs['metadata_path'].read_text())
        return {'run_id': 'result'}
    monkeypatch.setattr(durable, 'enqueue', enqueue)
    monkeypatch.setattr(geo_search, 'execute_expression_analysis', execute)
    selection = geo_search.AutomaticSelection(accession='GSE1', source_sha256='counts-hash', source_record_sha256='metadata-hash')
    result = asyncio.run(geo_search.run_geo_analysis(selection, 'alice'))
    assert captured['counts'] == 'gene\tGSM3\tGSM1\tGSM4\tGSM2\ngene1\t3\t1\t4\t2\n'
    assert list(csv.DictReader(io.StringIO(captured['metadata']), delimiter='\t'))[0]['condition'] == 'disease'
    if queue:
        assert captured['full_analysis'] is True and result['job_id'] == 'job'
    else:
        assert captured['stage'] == 'full' and result['execution_mode'] == 'hosted_R'


def test_source_metadata_changes_block_submission(monkeypatch):
    fake_sources(monkeypatch)
    selection = geo_search.AutomaticSelection(accession='GSE1', source_sha256='counts-hash', source_record_sha256='old-metadata')
    with pytest.raises(HTTPException) as caught:
        asyncio.run(geo_search.run_geo_analysis(selection, 'alice'))
    assert 'sample information changed' in caught.value.detail


def test_empty_R_preflight_output_is_not_missing_package(monkeypatch):
    expression._package_readiness.cache_clear()
    monkeypatch.setattr(expression.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, 0, '\n', ''))
    assert expression._package_readiness('test-R', False) == []
    expression._package_readiness.cache_clear()


def test_full_queue_execution_does_not_require_manual_QC_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setenv('BIONEXUS_EXPRESSION_ROOT', str(tmp_path / 'jobs'))
    monkeypatch.setattr(durable, 'readiness', lambda *a: {'available': True})
    counts = tmp_path / 'counts.tsv'; counts.write_text('gene\ts1\ng1\t1\n')
    meta = tmp_path / 'metadata.tsv'; meta.write_text('sample\tcondition\ns1\ta\n')
    job_id = durable.enqueue('alice', counts, meta, expression.ExpressionParameters(), {}, full_analysis=True)['job_id']
    captured = {}
    def execute(**kwargs): captured.update(kwargs); return {'run_id': 'full-run'}
    monkeypatch.setattr(durable, 'execute_expression_analysis', execute)
    job = durable.claim('worker'); durable.run_job(job)
    assert captured['stage'] == 'full' and captured['checkpoint_path'] is None
    with durable.db() as db:
        assert db.execute('SELECT state FROM jobs WHERE id=?', (job_id,)).fetchone()['state'] == 'SUCCEEDED'
