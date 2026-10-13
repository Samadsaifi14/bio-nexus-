import asyncio
import pytest
from fastapi import HTTPException
from app.services.workflow_collections import validate_protein_collection
from app.services.workflow_templates import WorkflowRecipe

@pytest.mark.parametrize('text', ['MKWVTF', '>a\nACTGACTG', '>a\nMKWVTX', '>a\nMKWVTF\n>a\nMKWVTF', '>a\nMK', '>bad/id\nMKWVTF', '>a\nMKWVT*', ''.join(f'>x{i}\nMKWVTF\n' for i in range(11))])
def test_rejects_bad_collections(text):
    with pytest.raises(ValueError):
        validate_protein_collection(text)

def test_preserves_unique_identifiers_and_normalizes_case():
    assert validate_protein_collection('>a description\nmkw vtf\n>b\nMKWVTF') == [
        {'identifier': 'a', 'sequence': 'MKWVTF'}, {'identifier': 'b', 'sequence': 'MKWVTF'}]

SUBMISSION = 'a6113c01-fca4-46f9-a136-417f201f39ef'

class FakeClient:
    def __init__(self, count=0):
        self.rows = {}; self.count = count; self.fail = set(); self.concurrent = False
    def table(self, name):
        client = self
        class Table:
            def __init__(self): self.filters = []
            def select(self, *args, **kwargs): return self
            def eq(self, key, value): self.filters.append((key, value)); return self
            def gte(self, *args): return self
            def update(self, payload): self.payload = payload; return self
            def execute(self):
                from types import SimpleNamespace
                rows = list(client.rows.values())
                for key, value in self.filters:
                    if key == 'context_json->>collection_id': rows = [r for r in rows if r['context_json']['collection_id'] == value]
                    else: rows = [r for r in rows if r.get(key) == value]
                if hasattr(self, "payload"):
                    for row in rows: row.update(self.payload)
                return SimpleNamespace(count=client.count, data=rows)
        return Table()

def setup_queue(monkeypatch, count=0):
    from app.routers import pipelines
    client = FakeClient(count); calls = []
    monkeypatch.setattr(pipelines, 'get_supabase', lambda: client)
    def enqueue(req, owner, *, job_id, collection_metadata):
        calls.append(job_id)
        if collection_metadata['collection_identifier'] in client.fail: raise RuntimeError('db')
        client.rows[job_id] = {'id': job_id, 'user_id': owner, 'status': 'queued', 'context_json': collection_metadata}
        if client.concurrent: raise RuntimeError('primary key conflict')
        return {'job_id': job_id, 'status': 'queued'}
    monkeypatch.setattr(pipelines, '_create_pipeline_job', enqueue)
    return pipelines, client, calls

def submit(pipelines, fasta='>a\nMKWVTF\n>b\nMKWVTF'):
    req = pipelines.WorkflowCollectionRequest(fasta=fasta, recipe=WorkflowRecipe(steps=['blast']), submission_id=SUBMISSION)
    return asyncio.run(pipelines.run_workflow_collection(None, req, 'owner'))

def test_validates_every_record_before_writes(monkeypatch):
    pipelines, client, calls = setup_queue(monkeypatch)
    with pytest.raises(HTTPException): submit(pipelines, '>a\nMKWVTF\n>b\nACTGACTG')
    assert not calls

def test_partial_retry_reuses_success_and_queues_only_missing(monkeypatch):
    pipelines, client, calls = setup_queue(monkeypatch)
    client.fail.add('b'); first = submit(pipelines)
    assert first['status'] == 'partial'
    assert [r['status'] for r in first['items']] == ['queued', 'submission_failed']
    client.fail.clear(); second = submit(pipelines)
    assert second['status'] == 'submitted' and second['items'][0]['reused']
    assert len(calls) == 3 and len(client.rows) == 2
    client.count = 10; third = submit(pipelines)
    assert all(r['reused'] for r in third['items']) and len(calls) == 3
    assert first['items'][0]['job_id'] == third['items'][0]['job_id']
    assert all(r['context_json']['input_sha256'] for r in client.rows.values())

def test_submission_id_content_mismatch_is_rejected(monkeypatch):
    pipelines, client, calls = setup_queue(monkeypatch); submit(pipelines)
    with pytest.raises(HTTPException) as exc: submit(pipelines, '>different\nMKWVTF')
    assert exc.value.status_code == 409 and len(calls) == 2

def test_concurrent_primary_key_conflict_reconciles_owned_matching_job(monkeypatch):
    pipelines, client, calls = setup_queue(monkeypatch); client.concurrent = True
    result = submit(pipelines)
    assert result['status'] == 'submitted' and all(r['reused'] for r in result['items'])
    assert len(client.rows) == 2

@pytest.mark.parametrize('count, expected', [(10, 429), (None, 503)])
def test_capacity_fail_closed_before_submission(monkeypatch, count, expected):
    pipelines, client, calls = setup_queue(monkeypatch, count)
    with pytest.raises(HTTPException) as exc: submit(pipelines)
    assert exc.value.status_code == expected and not calls

def test_all_failed_status(monkeypatch):
    pipelines, client, calls = setup_queue(monkeypatch); client.fail.update({'a', 'b'})
    assert submit(pipelines)['status'] == 'failed'


@pytest.mark.parametrize('state', ['complete', 'failed'])
def test_final_persistence_preserves_collection_then_retry_reuses(monkeypatch, state):
    from app.routers import pipeline_v2
    pipelines, client, calls = setup_queue(monkeypatch)
    result = submit(pipelines)
    monkeypatch.setattr(pipeline_v2, 'get_supabase', lambda: client)
    monkeypatch.setattr(pipeline_v2, '_mirror', lambda *_: None)
    for item in result['items']:
        client.rows[item['job_id']]['context_json']['blast'] = {'old': True}
        pipeline_v2._persist_v2_final(item['job_id'], state, {'blast': {'new': True}}, error='failure' if state == 'failed' else None)
        assert client.rows[item['job_id']]['context_json']['blast'] == {'new': True}
        assert client.rows[item['job_id']]['context_json']['collection_id'] == SUBMISSION
    again = submit(pipelines)
    assert all(i['reused'] and i['status'] == state for i in again['items'])
    assert len(calls) == 2


def test_final_single_job_preserves_execution_config_not_old_results(monkeypatch):
    from app.routers import pipeline_v2
    client = FakeClient(); job_id = '4935c407-878b-4b49-b8a9-f7eab95973a6'
    client.rows[job_id] = {'id': job_id, 'user_id': 'owner', 'context_json': {'workflow_steps': ['blast'], 'alignment_mode': 'local', 'blast': {'old': True}}}
    monkeypatch.setattr(pipeline_v2, 'get_supabase', lambda: client)
    monkeypatch.setattr(pipeline_v2, '_mirror', lambda *_: None)
    pipeline_v2._persist_v2_final(job_id, 'complete', {'blast': {'fresh': True}})
    assert client.rows[job_id]['context_json'] == {'workflow_steps': ['blast'], 'alignment_mode': 'local', 'blast': {'fresh': True}}
