import asyncio
import hashlib
import pytest
from pydantic import ValidationError
from fastapi import HTTPException
from app.services.workflow_templates import WorkflowRecipe, recipe_from_experiment, recipe_plan


def test_dependency_validation_and_planned_state():
    recipe = WorkflowRecipe(steps=['phylo', 'msa', 'blast'], alignment_mode='local')
    assert recipe.steps == ['blast', 'msa', 'phylo']
    assert all(step['state'] == 'NOT_EXECUTED' for step in recipe_plan(recipe)['steps'])
    for steps in (['phylo'], ['blast', 'blast'], ['shell'], []):
        with pytest.raises(ValidationError):
            WorkflowRecipe(steps=steps)
    with pytest.raises(ValidationError):
        WorkflowRecipe(steps=['blast'], command='rm -rf /')


def test_recipe_preserves_parameters_and_rejects_unrecorded_configuration():
    source = {'pipeline': 'protein_analysis', 'parameters': {'steps': ['blast', 'msa'],
        'alignment_mode': 'local', 'fast_mode': True,
        'blast_params': {'database': 'swissprot', 'program': 'blastp', 'max_hits': 5, 'query_accession': ''}}}
    recipe = recipe_from_experiment(source)
    assert recipe.max_hits == 5 and recipe.alignment_mode == 'local' and recipe.fast_mode
    assert WorkflowRecipe.model_validate(recipe.model_dump()) == recipe
    with pytest.raises(ValueError):
        recipe_from_experiment({'pipeline': 'protein_analysis', 'parameters': {}})
    with pytest.raises(ValueError):
        recipe_from_experiment({'pipeline': 'arbitrary_script', 'parameters': source['parameters']})


def test_replay_foreign_job_never_reads_source(monkeypatch):
    from app.routers import experiments
    monkeypatch.setattr(experiments, 'owns_job', lambda *_: False)
    monkeypatch.setattr(experiments, 'get_experiment', lambda *_: pytest.fail('Unauthorized read'))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(experiments.replay_workflow('foreign', experiments.ReplayExperimentRequest(sequence='MKWVTF'), None, 'user'))
    assert exc.value.status_code == 404


def test_replay_verifies_checksum_then_creates_owned_queued_job(monkeypatch):
    from app.routers import experiments, pipelines
    source = {'experiment_id': 'e', 'pipeline': 'protein_analysis',
        'input_hash': hashlib.sha256(b'MKWVTF').hexdigest(),
        'parameters': {'steps': ['blast'], 'fast_mode': False, 'alignment_mode': 'global', 'blast_params': {'max_hits': 3, 'database': '', 'program': '', 'query_accession': ''}}}
    monkeypatch.setattr(experiments, 'owns_job', lambda *_: True)
    monkeypatch.setattr(experiments, 'get_experiment', lambda *_: source)
    calls = []
    def enqueue(req, user_id, parent_job_id=None):
        calls.append((req, user_id, parent_job_id))
        return {'job_id': 'new', 'status': 'queued'}
    monkeypatch.setattr(pipelines, '_create_pipeline_job', enqueue)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(experiments.replay_workflow('old', experiments.ReplayExperimentRequest(sequence='AAAAAA'), None, 'u'))
    assert exc.value.status_code == 409 and not calls
    result = asyncio.run(experiments.replay_workflow('old', experiments.ReplayExperimentRequest(sequence='>input\nMKWVTF'), None, 'u'))
    assert result['status'] == 'queued' and result['source_experiment_id'] == 'e'
    assert calls[0][1:] == ('u', 'old')
    assert calls[0][0].workflow_recipe.max_hits == 3


def test_worker_entry_preserves_subset_and_collects_actual_context(monkeypatch):
    from app.routers import pipeline_v2
    async def execute(job_id, sequence, steps, **kwargs):
        assert steps == ['blast', 'msa'] and kwargs['alignment_mode'] == 'local'
        pipeline_v2._set_step_status(job_id, 'msa', 'complete', data={'actual': 'result'})
    monkeypatch.setattr(pipeline_v2, '_execute', execute)
    result = asyncio.run(pipeline_v2.run_pipeline('MKWVTF', steps=['blast', 'msa'], alignment_mode='local'))
    assert result['msa'] == {'actual': 'result'}
    assert not any(key.startswith('worker-') for key in pipeline_v2._jobs)


def test_recipe_queue_retains_full_input_config_and_atomic_parent_lineage(monkeypatch):
    from app.routers import pipelines
    rows = []
    class Table:
        def insert(self, row):
            rows.append(row)
            return self
        def execute(self):
            return None
    class Client:
        def table(self, table):
            assert table == 'jobs'
            return Table()
    monkeypatch.setattr(pipelines, 'get_supabase', lambda: Client())
    recipe = WorkflowRecipe(steps=['blast', 'msa'], program='blastp', max_hits=4, alignment_mode='local')
    req = pipelines.PipelineRunRequest(sequence='>test\nMKWVTF', workflow_recipe=recipe)
    result = pipelines._create_pipeline_job(req, 'owner', parent_job_id='source')
    row = rows[0]
    assert result['status'] == row['status'] == 'queued'
    assert row['user_id'] == 'owner' and row['parent_job_id'] == 'source'
    assert row['context_json']['sequence'] == 'MKWVTF'
    assert row['context_json']['workflow_steps'] == ['blast', 'msa']
    assert row['context_json']['alignment_mode'] == 'local'
    assert row['context_json']['max_hits'] == 4
    assert 'MKWVTF' not in row['query_preview']
    with pytest.raises(HTTPException):
        pipelines._create_pipeline_job(pipelines.PipelineRunRequest(sequence='ACTGACTG', workflow_recipe=recipe), 'owner')
    assert len(rows) == 1
