from app.services.evidence_graph import assemble_evidence


def test_evidence_graph_exposes_full_reviewer_path_without_breaking_legacy_edges():
    context = {
        "uniprot": {
            "accession": "P68871",
            "version": "reviewed-record",
            "parameters": {"accession": "P68871"},
            "benchmark_refs": ["ANN-UNIPROT"],
        },
        "interpret": {"interpretation": "The UniProt accession P68871 is present in the recorded evidence."},
    }
    graph = assemble_evidence(context)
    assert graph["schema"] == "bionexus-evidence-graph/v3"
    assert graph["reviewer_path"] == [
        "claim", "evidence", "algorithm", "database", "version", "parameters", "confidence", "benchmark"
    ]

    # Backward compatibility: legacy edges remain source -> claim.
    assert graph["edges"]
    assert graph["edges"][0]["from"] == "uniprot"
    assert graph["edges"][0]["to"].startswith("claim-")

    node_types = {node["type"] for node in graph["nodes"]}
    assert set(graph["reviewer_path"]).issubset(node_types)
    relations = {edge["relation"] for edge in graph["typed_edges"]}
    assert {"supported_by", "generated_by", "uses_database", "has_version", "executed_with", "contributes_to_confidence", "evaluated_by"}.issubset(relations)


def test_evidence_graph_marks_missing_benchmark_explicitly():
    context = {
        "sequence": {"sequence_length": 4, "tool_version": "1.0"},
        "interpret": {"interpretation": "The recorded sequence_length is 4."},
    }
    graph = assemble_evidence(context)
    benchmark_nodes = [n for n in graph["nodes"] if n["type"] == "benchmark"]
    assert benchmark_nodes
    assert any(n["data"].get("status") == "not_recorded" for n in benchmark_nodes)
