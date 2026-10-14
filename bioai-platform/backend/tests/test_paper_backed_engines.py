import asyncio
import hashlib
import io
import json
import os
import shutil
import zipfile

import pytest
from fastapi import HTTPException
from app.ngs.nextflow_trace import parse_trace, observe_trace
from app.ngs.execution import _artifact_groups
from app.services.local_similarity import parse_protein_fasta, parse_hits, search, SimilarityError, EngineUnavailable
from app.services.workflow_rocrate import build_workflow_rocrate
from app.tools.alignment_significance import alignment_score_test
from app.tools.pairwise_alignment import PairwiseAlignError
from app.routers.interactions import _json_score

HEADER = b'task_id\tname\tstatus\texit\tduration\n'


def test_trace_keeps_cached_failed_and_unfinished_evidence_distinct():
    body = HEADER + b'1\tFASTQC(sample)\tCOMPLETED\t0\t3s\n2\tSTAR(sample)\tCACHED\t-\t-\n3\tSALMON(sample)\tCOMPLETED\t1\t1s\n4\tONGOING'
    result = parse_trace(body)
    assert result['observed_process_records'] == 3
    assert result['states']['COMPLETED'] == 1 and result['states']['CACHED'] == 1 and result['states']['FAILED'] == 1
    assert result['incomplete_last_record']
    assert result['trace_sha256'] == hashlib.sha256(body).hexdigest()


@pytest.mark.parametrize('body', [b'other\n', HEADER + b'1\tn\tCOMPLETED\tbad\t-\n', HEADER + b'1\tn\tCOMPLETED\n'])
def test_invalid_trace_never_becomes_success(body):
    with pytest.raises(ValueError): parse_trace(body)


def test_trace_path_cannot_escape_owned_output(tmp_path):
    root = tmp_path / 'run'; (root / 'pipeline_info').mkdir(parents=True)
    secret = tmp_path / 'external.txt'; secret.write_bytes(HEADER + b'1\tOTHER\tCOMPLETED\t0\t-\n')
    (root / 'pipeline_info' / 'execution_trace.txt').symlink_to(secret)
    assert observe_trace(str(root))['state'] == 'NOT_EMITTED'
    assert observe_trace('s3://bucket/run')['state'] == 'UNAVAILABLE'


def test_counts_are_not_satisfied_by_tpm_or_scaled_estimates():
    files = ['run/salmon/salmon.merged.gene_tpm.tsv', 'run/salmon/salmon.merged.gene_counts_length_scaled.tsv']
    groups = _artifact_groups('nf-core/rnaseq', files)
    assert groups['count_candidates'] == []
    assert groups['normalized_expression'] == files[:1]
    assert groups['scaled_count_estimates'] == files[1:]
    original = 'run/salmon/salmon.merged.gene_counts.tsv'
    assert _artifact_groups('nf-core/rnaseq', files + [original])['count_candidates'] == [original]


def test_rocrate_preserves_unknown_steps_and_payload_hash():
    body = build_workflow_rocrate({'experiment_id':'e', 'status':'complete'}, [
        {'node_id':'searched','tool':'DIAMOND','tool_version':'2.1.18','status':'complete'},
        {'node_id':'not-run','tool':'folding','status':'pending'}])
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        assert set(archive.namelist()) == {'README.txt','ro-crate-metadata.json','workflow-evidence.json'}
        nodes = {n['@id']:n for n in json.loads(archive.read('ro-crate-metadata.json'))['@graph']}
        assert nodes['ro-crate-metadata.json']['about'] == {'@id':'./'}
        assert nodes['ro-crate-metadata.json']['conformsTo']['@id'].endswith('/1.1')
        assert nodes['#step-1']['@type'] == 'CreativeWork' and 'actionStatus' not in nodes['#step-1']
        assert nodes['workflow-evidence.json']['identifier'] == 'urn:sha256:' + hashlib.sha256(archive.read('workflow-evidence.json')).hexdigest()
        evidence = json.loads(archive.read('workflow-evidence.json'))
        assert evidence['reproducibility_gaps'] and not evidence['execution']['executable']


def test_rocrate_foreign_owner_is_denied_before_provenance_access(monkeypatch):
    from app.routers import experiments
    monkeypatch.setattr(experiments, 'owns_job', lambda *_: False)
    monkeypatch.setattr(experiments, 'get_experiment', lambda *_: pytest.fail('unowned experiment read'))
    with pytest.raises(HTTPException) as error:
        asyncio.run(experiments.export_rocrate('foreign', 'alice'))
    assert error.value.status_code == 404


@pytest.mark.parametrize('text', ['MKWVTFISLL', '>a\nMKWVTFISLL\n>a\nMKWVTFISLL', '>a\nACD*EFGHIKL', '>\nMKWVTFISLL'])
def test_invalid_custom_reference_is_rejected(text):
    with pytest.raises(SimilarityError): parse_protein_fasta(text)


def test_diamond_parser_preserves_small_evalues_and_rejects_bad_coordinates():
    refs = {'hit':{'sequence':'MKWVTFISLL','description':'hit protein'}}
    result = parse_hits('hit\t100\t10\t1\t10\t1\t10\t1e-320\t40\t100', refs, 10)
    assert result[0]['evalue_raw'] == '1e-320' and result[0]['query_coverage_pct'] == 100
    with pytest.raises(SimilarityError): parse_hits('hit\t100\t10\t0\t10\t1\t10\t1e-3\t40\t100', refs, 10)
    with pytest.raises(SimilarityError): parse_hits('hit\t100\t10\t1\t10\t1\t10\tnan\t40\t100', refs, 10)


def test_missing_diamond_is_an_engine_failure(monkeypatch):
    monkeypatch.setattr(shutil, 'which', lambda _: None)
    with pytest.raises(EngineUnavailable): search('>q\nMKWVTFISLL', '>h\nMKWVTFISLL')


@pytest.mark.skipif(not shutil.which(os.environ.get('BIONEXUS_DIAMOND','diamond')), reason='native DIAMOND engine not installed')
def test_native_diamond_exact_reference_and_true_no_hit():
    seq = 'MVHLTPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRFFESFGDLSTPDAVMGNPKVKAHGKKVLGAFSDGLAHLDNLKGTFATLSELHCDKLHVDPENFRLLGNVLVCVLAHHFGKEFTPPVQAAYQKVVAGVANALAHKYH'
    result = search('>q\n'+seq, '>known\n'+seq)
    assert result['search_complete'] and result['hits'][0]['identity_pct'] == 100
    assert result['hits'][0]['query_coverage_pct'] == 100 and len(result['provenance']['engine_sha256']) == 64
    nohit = search('>q\n' + 'ACDEFGHIKLMNPQRSTVWY'*5, '>known\n'+seq)
    assert nohit['status'] == 'SUCCEEDED' and nohit['search_complete'] and nohit['hits'] == []


def test_shuffle_test_ties_give_one_and_pvalues_cannot_be_zero():
    ties = alignment_score_test('AAAAAAAAAA','AAAAAAAAAA',permutations=19)
    assert ties['p_value'] == 1 and ties['exceedances'] == 19
    seq = 'MKWVTFISLLFLFSSAYS'
    result = alignment_score_test(seq, seq, permutations=99, seed=7)
    assert result['p_value'] >= 0.01 and result == alignment_score_test(seq, seq, permutations=99, seed=7)
    assert result['p_value'] == (result['exceedances'] + 1) / 100 and len(result['null_scores']) == 99


def test_shuffle_test_limits_fail_before_expensive_work():
    with pytest.raises(PairwiseAlignError): alignment_score_test('A'*1000,'A'*1000,permutations=999)
    with pytest.raises(PairwiseAlignError): alignment_score_test('MKWVTFISLL','MKWVTFISLL',permutations=0)


def test_string_json_scores_preserve_provider_scale():
    assert _json_score(0.999) == 0.999 and _json_score(0.9) == 0.9 and _json_score(0) == 0
    for value in (999, -0.1, float('nan'), True, 'bad'):
        with pytest.raises(HTTPException): _json_score(value)


def test_production_monitor_denies_foreign_run_before_trace_read(monkeypatch):
    from app.routers import ngs_v2
    def denied(*args): raise FileNotFoundError('run')
    monkeypatch.setattr(ngs_v2, 'get_run', denied)
    with pytest.raises(HTTPException) as error:
        ngs_v2.production_execution_monitor('foreign', 'alice')
    assert error.value.status_code == 404
