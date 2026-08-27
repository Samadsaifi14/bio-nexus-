"""Tool card manifests — machine-readable metadata for every tool in the platform."""

import json
from pathlib import Path

TOOL_CARDS_PATH = Path(__file__).parent / "tool_cards.json"

TOOL_CARDS = [
    {
        "id": "blast",
        "name": "NCBI BLAST",
        "category": "sequence_search",
        "inputs": {"sequence": "string", "database": "string", "program": "string", "max_hits": "integer"},
        "outputs": {"hits": "array<BlastHit>", "statistics": "object"},
        "external": "NCBI BLAST API (blastp, blastx, tblastn)",
        "version": "2.16.0+",
        "cli_binary": None,
        "api_endpoint": "/api/pipelines/run",
    },
    {
        "id": "uniprot",
        "name": "UniProt REST",
        "category": "annotation",
        "inputs": {"accession": "string"},
        "outputs": {"annotation": "UniprotSummary"},
        "external": "REST API (rest.uniprot.org)",
        "version": "2024_02",
        "cli_binary": None,
        "api_endpoint": "/api/uniprot/{accession}",
    },
    {
        "id": "msa",
        "name": "Multiple Sequence Alignment",
        "category": "alignment",
        "inputs": {"query_sequence": "string", "hit_sequences": "array<string>", "mode": "global|local"},
        "outputs": {"alignment_fasta": "string", "phylotree": "newick_string"},
        "external": "Local MAFFT → EBI Clustal Omega → in-process fallback",
        "version": "7.526",
        "cli_binary": "/usr/local/bin/mafft",
        "api_endpoint": None,
    },
    {
        "id": "phylo",
        "name": "Phylogenetic Tree",
        "category": "phylogeny",
        "inputs": {"alignment_fasta": "string", "method": "string"},
        "outputs": {"newick_tree": "string"},
        "external": "PhyML via BioPython TreeConstruction",
        "version": "20240611",
        "cli_binary": "/usr/local/bin/phyml",
        "api_endpoint": "/api/phylo/tree",
    },
    {
        "id": "domains",
        "name": "Protein Domain Analysis",
        "category": "annotation",
        "inputs": {"accession": "string", "sequence": "string"},
        "outputs": {"domains": "array<Domain>", "go_terms": "array<string>"},
        "external": "InterProScan5 REST API → InterPro2GO mapping",
        "version": "5.69-101.0",
        "cli_binary": None,
        "api_endpoint": "/api/domains/{accession}",
    },
    {
        "id": "pathway_enrichment",
        "name": "Pathway Enrichment",
        "category": "function",
        "inputs": {"gene_list": "array<string>", "species": "string"},
        "outputs": {"pathways": "array<Pathway>", "token": "string"},
        "external": "Reactome API + g:Profiler REST API",
        "version": "g:2024.1",
        "cli_binary": None,
        "api_endpoint": "/api/pathways/enrichment",
    },
    {
        "id": "alphafold",
        "name": "AlphaFold Structure",
        "category": "structure",
        "inputs": {"uniprot_accession": "string"},
        "outputs": {"pdb_url": "string", "cif_url": "string", "confidence": "float"},
        "external": "AlphaFold DB REST API (alphafold.ebi.ac.uk)",
        "version": "v4",
        "cli_binary": None,
        "api_endpoint": None,
    },
    {
        "id": "interpret",
        "name": "AI Interpretation",
        "category": "analysis",
        "inputs": {"context": "AssembledContext"},
        "outputs": {"report": "FinalSynthesisReport"},
        "external": "OpenAI GPT-4o via LiteLLM proxy",
        "version": "gpt-4o",
        "cli_binary": None,
        "api_endpoint": "/api/ai/interpret",
    },
    {
        "id": "interactions",
        "name": "Protein-Protein Interactions",
        "category": "network",
        "inputs": {"gene": "string", "species": "integer", "network_type": "functional|physical"},
        "outputs": {"interactions": "array<InteractionPartner>"},
        "external": "STRING DB REST API (string-db.org)",
        "version": "12.0",
        "cli_binary": None,
        "api_endpoint": "/api/interactions/{gene}",
    },
    {
        "id": "docking",
        "name": "Molecular Docking",
        "category": "docking",
        "inputs": {"pdb_id": "string", "smiles": "string", "protein_sequence": "string"},
        "outputs": {"affinity": "float", "modes": "array<DockMode>", "sdf": "string"},
        "external": "AutoDock Vina + Gnina CNN rescoring",
        "version": "Vina 1.2.5 / Gnina 1.3.2",
        "cli_binary": "/usr/local/bin/vina; /usr/local/bin/gnina",
        "api_endpoint": "/api/docking/run",
    },
    {
        "id": "structure_prep",
        "name": "Structure Preparation",
        "category": "structure",
        "inputs": {"pdb_id": "string", "probe_radius": "float"},
        "outputs": {"pockets": "array<Pocket>", "chain_integrity": "string"},
        "external": "fpocket 4.2.3 + BioPython SASA fallback",
        "version": "4.2.3",
        "cli_binary": "/usr/local/bin/fpocket",
        "api_endpoint": "/api/structure-prep/run",
    },
    {
        "id": "castp",
        "name": "CASTp Pocket Analysis",
        "category": "structure",
        "inputs": {"pdb_id": "string"},
        "outputs": {"pockets": "array<PocketInfo>", "total_pockets": "integer"},
        "external": "fpocket 4.2.3 (real binary) + BioPython SASA fallback",
        "version": "4.2.3",
        "cli_binary": "/usr/local/bin/fpocket",
        "api_endpoint": "/api/castp/analyze",
    },
    {
        "id": "function_predict",
        "name": "Protein Function Prediction",
        "category": "function",
        "inputs": {"sequence": "string", "accession": "string"},
        "outputs": {"go_terms": "array<string>", "domains": "array<Domain>", "source": "string"},
        "external": "InterProScan5 REST API + InterPro2GO mapping",
        "version": "5.69-101.0",
        "cli_binary": None,
        "api_endpoint": "/api/function/predict",
    },
    {
        "id": "ngs",
        "name": "NGS Quality Control",
        "category": "sequencing",
        "inputs": {"fastq_url": "string", "reference": "string"},
        "outputs": {"quality": "object", "alignments": "array<Alignment>"},
        "external": "FastQC + BioPython alignment",
        "version": "0.12.1",
        "cli_binary": "/usr/local/bin/fastqc",
        "api_endpoint": "/api/ngs/run",
    },
    {
        "id": "md",
        "name": "Molecular Dynamics",
        "category": "simulation",
        "inputs": {"pdb_id": "string", "forcefield": "string", "steps": "integer"},
        "outputs": {"trajectory": "string", "energy": "float"},
        "external": "OpenMM + BioPython fallback",
        "version": "8.0",
        "cli_binary": None,
        "api_endpoint": "/api/md/run",
    },
    {
        "id": "primers",
        "name": "Primer Design",
        "category": "pcr",
        "inputs": {"template_sequence": "string", "target_region": "string"},
        "outputs": {"primers": "array<Primer>", "product_size": "integer"},
        "external": "In-process BioPython calculation",
        "version": "1.83",
        "cli_binary": None,
        "api_endpoint": "/api/primers/design",
    },
    {
        "id": "swissmodel",
        "name": "Homology Modeling",
        "category": "structure",
        "inputs": {"sequence": "string", "template": "string"},
        "outputs": {"model_pdb": "string", "qmeandiscore": "float"},
        "external": "SwissModel Workspace API",
        "version": "2024-03",
        "cli_binary": None,
        "api_endpoint": "/api/swissmodel/model",
    },
    {
        "id": "admet",
        "name": "ADMET Properties",
        "category": "drug_discovery",
        "inputs": {"smiles": "string"},
        "outputs": {"properties": "object", "violations": "array<string>"},
        "external": "RDKit + pkCSM",
        "version": "2024.03",
        "cli_binary": None,
        "api_endpoint": "/api/admet/predict",
    },
]


def get_tool_cards() -> list[dict]:
    return TOOL_CARDS


def get_tool_card(tool_id: str) -> dict | None:
    for card in TOOL_CARDS:
        if card["id"] == tool_id:
            return card
    return None


def write_tool_cards():
    """Write tool_cards.json to disk for static consumption."""
    TOOL_CARDS_PATH.write_text(json.dumps(TOOL_CARDS, indent=2))


if __name__ == "__main__":
    write_tool_cards()
    print(f"Wrote {len(TOOL_CARDS)} tool cards to {TOOL_CARDS_PATH}")
