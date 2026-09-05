"""Publication Engine (Component 10) unit tests — pure context→paper, no DB."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.publication import (
    JOURNAL_TEMPLATES,
    render_markdown,
    render_paper,
    section_snapshot,
)

P53 = {
    "query": {"accession": "P04637"},
    "blast": {
        "count": 12,
        "program": "blastp",
        "database": "swissprot",
        "top_hit": {"accession": "P04637", "description": "Cellular tumor antigen p53", "identity_pct": 100.0, "evalue": 1e-180},
    },
    "uniprot": {"accession": "P04637", "full_name": "Cellular tumor antigen p53", "gene_names": ["TP53"], "organism": "Homo sapiens"},
    "msa": {"sequence_count": 6, "method": "clustalo"},
    "domains": {"sequence_length": 393, "domains": [{"accession": "IPR012345", "name": "p53", "start": 92, "end": 292}], "count": 1},
    "alphafold": {"structure_available": True, "confidence": 87.4, "pdb_url": "https://alphafold.ebi.ac.uk/entry/P04637"},
    "interpret": {"interpretation": "Query is p53. DNA-binding domain present. The exact cavity is unresolved."},
}


def test_section_snapshot_keys():
    snap = section_snapshot(P53)
    assert snap["blast"]["top_hit"] == "P04637"
    assert snap["domains"]["count"] == 1  # derived from domains list
    assert snap["msa"]["sequence_count"] == 6
    assert snap["alphafold"]["structure_available"] is True


def test_render_paper_has_manuscript_sections():
    paper = render_paper(P53, "exp-x")
    for section in ("title", "abstract", "methods", "results", "statistics",
                    "figures", "supplementary", "data_availability",
                    "code_availability", "declarations", "references", "journal_formats"):
        assert section in paper
    assert paper["statistics"]["blast"]["top_hit"] == "P04637"


def test_render_paper_references_non_empty():
    paper = render_paper(P53, "exp-x")
    assert paper["references"], "papers must cite the tools that produced the results"


def test_render_paper_figures_from_experiment():
    paper = render_paper(P53, "exp-x")
    assert paper["figures"][0]["figure"] == "Figure 1"
    assert "exp-x" in paper["figures"][0]["source"]


def test_render_paper_empty_context_degrades():
    paper = render_paper(None, "empty")
    assert paper["title"]
    assert paper["results"]  # honest degradation, no traceback


def test_render_markdown_structure():
    paper = render_paper(P53, "exp-x")
    md = render_markdown(paper, journal="bmc")
    assert md.startswith("Cellular tumor antigen p53")
    for heading in ("## Abstract", "## Background", "## Methods", "## Results",
                    "## Figures", "## Data availability", "## References"):
        assert heading in md


def test_journal_templates_defined():
    assert "nature" in JOURNAL_TEMPLATES and "bmc" in JOURNAL_TEMPLATES
    assert JOURNAL_TEMPLATES["nature"]["sections"]