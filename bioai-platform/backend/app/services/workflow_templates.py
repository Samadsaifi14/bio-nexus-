"""Portable built-in workflow recipes. Recipes are configuration, never evidence."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

STEP_ORDER = ['blast', 'uniprot', 'msa', 'phylo', 'domains', 'pathway_enrichment', 'alphafold', 'interpret']
DEPENDENCIES = {'uniprot': ['blast'], 'msa': ['blast'], 'phylo': ['msa'],
                'domains': ['blast'], 'pathway_enrichment': ['blast'],
                'alphafold': ['uniprot'], 'interpret': ['blast']}

class WorkflowRecipe(BaseModel):
    model_config = ConfigDict(extra='forbid')
    format: Literal['bionexus-workflow-recipe'] = 'bionexus-workflow-recipe'
    schema_version: Literal[1] = 1
    pipeline: Literal['protein_analysis'] = 'protein_analysis'
    steps: list[str] = Field(min_length=1, max_length=8)
    database: str = Field(default='', max_length=100)
    program: Literal['', 'blastp'] = ''
    max_hits: int = Field(default=100, ge=1, le=100)
    fast_mode: bool = False
    alignment_mode: Literal['global', 'local'] = 'global'
    query_accession: str = Field(default='', max_length=100)

    @model_validator(mode='after')
    def validate_graph(self):
        if len(set(self.steps)) != len(self.steps) or any(s not in STEP_ORDER for s in self.steps):
            raise ValueError('Steps must be unique built-in protein workflow steps')
        for step in self.steps:
            if any(dep not in self.steps for dep in DEPENDENCIES.get(step, [])):
                raise ValueError(f'{step} requires {DEPENDENCIES[step]}')
        self.steps = [step for step in STEP_ORDER if step in self.steps]
        return self


def recipe_from_experiment(experiment: dict) -> WorkflowRecipe:
    if experiment.get('pipeline') != 'protein_analysis':
        raise ValueError('Only recorded protein_analysis workflows support replay')
    params = experiment.get('parameters')
    if not isinstance(params, dict) or not isinstance(params.get('steps'), list):
        raise ValueError('Recorded workflow step configuration is missing; replay cannot infer it')
    if any(key not in params for key in ('fast_mode', 'alignment_mode', 'blast_params')):
        raise ValueError('Recorded execution parameters are incomplete; replay cannot infer defaults')
    blast = params.get('blast_params') or {}
    if not isinstance(blast, dict):
        raise ValueError('Recorded BLAST parameters are invalid')
    if any(key not in blast for key in ('database', 'program', 'max_hits', 'query_accession')):
        raise ValueError('Recorded BLAST configuration is incomplete; replay cannot infer defaults')
    return WorkflowRecipe(steps=params['steps'], fast_mode=params.get('fast_mode', False),
                          alignment_mode=params.get('alignment_mode', 'global'),
                          **{key: blast[key] for key in ('database', 'program', 'max_hits', 'query_accession') if key in blast})


def recipe_plan(recipe: WorkflowRecipe) -> dict:
    return {'recipe': recipe.model_dump(), 'state': 'PLANNED', 'executable': True,
            'executor': 'bionexus-protein-worker',
            'steps': [{'id': step, 'state': 'NOT_EXECUTED', 'depends_on': DEPENDENCIES.get(step, [])} for step in recipe.steps],
            'limits': ['External providers and databases may change between runs.',
                       'Replay creates a new job; it does not guarantee identical scientific output.',
                       'No Galaxy, Nextflow, WDL or Seqera import compatibility is claimed.']}
