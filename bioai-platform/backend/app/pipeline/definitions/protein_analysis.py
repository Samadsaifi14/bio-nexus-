from typing import Any

PIPELINE_DEFINITION = {
    "id": "protein_analysis",
    "name": "Protein Sequence Analysis",
    "description": "Analyze a protein sequence: BLAST against Swiss-Prot, fetch UniProt annotations, retrieve AlphaFold structure",
    "input_type": "sequence",
    "input_label": "Protein sequence (FASTA or plain)",
    "steps": ["blast", "uniprot", "alphafold"],
    "default_database": "uniprotkb_swissprot",
    "default_max_hits": 10,
}


def get_pipeline_definition() -> dict:
    return PIPELINE_DEFINITION
