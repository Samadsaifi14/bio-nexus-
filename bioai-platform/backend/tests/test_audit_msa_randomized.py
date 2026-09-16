"""Independent deterministic audit checks for BioNexus MSA resilience paths."""

from __future__ import annotations

import random
from io import StringIO
from types import SimpleNamespace

import pytest
from Bio import Phylo

from app.tools import mafft_local
from app.tools.msa_fallback import (
    _aligner,
    _pairwise,
    _upgma_newick,
    progressive_msa,
)

SEED = 20260916


def _parse_alignment(fasta: str) -> dict[str, str]:
    records: dict[str, str] = {}
    current = None
    for raw in fasta.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            current = line[1:].split()[0]
            assert current not in records
            records[current] = ""
        else:
            assert current is not None
            records[current] += line.upper()
    return records


def test_pairwise_fallback_preserves_residues_and_alignment_length():
    g1, g2 = _pairwise(_aligner("dna"), "ACGT", "ACGTT")
    assert len(g1) == len(g2)
    assert g1.replace("-", "") == "ACGT"
    assert g2.replace("-", "") == "ACGTT"
    assert "-" in g1


def test_upgma_branch_lengths_are_ultrametric_for_known_matrix():
    labels = ["A", "B", "C"]
    dist = [
        [0.0, 0.2, 0.8],
        [0.2, 0.0, 0.8],
        [0.8, 0.8, 0.0],
    ]
    newick = _upgma_newick(labels, dist)
    tree = Phylo.read(StringIO(newick), "newick")
    leaves = {leaf.name: leaf for leaf in tree.get_terminals()}
    root_distances = {name: tree.distance(tree.root, leaf) for name, leaf in leaves.items()}
    assert set(leaves) == set(labels)
    assert root_distances["A"] == pytest.approx(0.4, abs=1e-6)
    assert root_distances["B"] == pytest.approx(0.4, abs=1e-6)
    assert root_distances["C"] == pytest.approx(0.4, abs=1e-6)


def test_upgma_rejects_invalid_distance_contracts():
    with pytest.raises(ValueError, match="dimensions"):
        _upgma_newick(["A", "B"], [[0.0]])
    with pytest.raises(ValueError, match="symmetric"):
        _upgma_newick(["A", "B"], [[0.0, 0.1], [0.2, 0.0]])
    with pytest.raises(ValueError, match="non-negative"):
        _upgma_newick(["A", "B"], [[0.0, -0.1], [-0.1, 0.0]])


def test_progressive_fallback_rejects_duplicate_and_unsafe_ids():
    with pytest.raises(ValueError, match="Duplicate"):
        progressive_msa([("a", "ACGT"), ("a", "ACGA")], "dna")
    with pytest.raises(ValueError, match="identifier"):
        progressive_msa([("a,1", "ACGT"), ("b", "ACGA")], "dna")


def test_seeded_progressive_fallback_preserves_every_sequence_and_taxon():
    rng = random.Random(SEED)
    for replicate in range(20):
        source: list[tuple[str, str]] = []
        for index in range(rng.randint(2, 6)):
            length = rng.randint(8, 24)
            sequence = "".join(rng.choice("ACGT") for _ in range(length))
            source.append((f"r{replicate}_s{index}", sequence))

        aligned_fasta, newick = progressive_msa(source, "dna")
        aligned = _parse_alignment(aligned_fasta)
        assert set(aligned) == {sid for sid, _ in source}
        assert len({len(seq) for seq in aligned.values()}) == 1
        for sid, original in source:
            assert aligned[sid].replace("-", "") == original

        tree = Phylo.read(StringIO(newick), "newick")
        leaves = [leaf.name for leaf in tree.get_terminals()]
        assert sorted(leaves) == sorted(sid for sid, _ in source)
        assert len(leaves) == len(set(leaves))


def test_mafft_strategy_flags_match_canonical_v7_definitions():
    assert mafft_local.STRATEGY_FLAGS["fft-ns-2"] == ["--retree", "2", "--maxiterate", "0"]
    assert mafft_local.STRATEGY_FLAGS["fft-ns-i"] == ["--maxiterate", "1000"]
    assert mafft_local.STRATEGY_FLAGS["l-ins-i"] == ["--localpair", "--maxiterate", "1000"]
    assert mafft_local.STRATEGY_FLAGS["g-ins-i"] == ["--globalpair", "--maxiterate", "1000"]
    assert mafft_local.STRATEGY_FLAGS["e-ins-i"] == ["--genafpair", "--maxiterate", "1000"]


def test_local_mafft_command_and_output_integrity(monkeypatch):
    fasta = ">a\nACGT\n>b\nACGTT\n"
    alignment = ">a\nACG-T\n>b\nACGTT\n"
    calls: list[list[str]] = []

    monkeypatch.setattr(mafft_local, "_ensure_mafft", lambda: "/fake/mafft")
    monkeypatch.setattr(mafft_local, "_MAFFT_VERSION", None)

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        if "--version" in cmd:
            return SimpleNamespace(returncode=0, stdout="v7.526 (2024/Apr/26)\n", stderr="")
        return SimpleNamespace(returncode=0, stdout=alignment, stderr="")

    monkeypatch.setattr(mafft_local.subprocess, "run", fake_run)
    result = mafft_local.run_local_mafft(fasta, strategy="e-ins-i", threads=2, timeout=30)
    assert result is not None
    assert result["aln_fasta"] == alignment
    assert result["strategy"] == "e-ins-i"
    assert result["threads"] == 2
    assert result["tool_version"] == "7.526"
    execution = next(call for call in calls if "--version" not in call)
    assert execution[0] == "/fake/mafft"
    assert "--genafpair" in execution
    assert "--maxiterate" in execution and "1000" in execution
    assert "--thread" in execution and "2" in execution


def test_local_mafft_rejects_malformed_or_residue-changing_output(monkeypatch):
    fasta = ">a\nACGT\n>b\nACGTT\n"
    monkeypatch.setattr(mafft_local, "_ensure_mafft", lambda: "/fake/mafft")

    outputs = iter([
        ">a\nACGT\n",  # missing b
        ">a\nACG-T\n>b\nACGTA\n",  # b residue changed
    ])

    def fake_run(cmd, **kwargs):
        if "--version" in cmd:
            return SimpleNamespace(returncode=0, stdout="v7.526\n", stderr="")
        return SimpleNamespace(returncode=0, stdout=next(outputs), stderr="")

    monkeypatch.setattr(mafft_local.subprocess, "run", fake_run)
    assert mafft_local.run_local_mafft(fasta) is None
    assert mafft_local.run_local_mafft(fasta) is None


def test_local_mafft_rejects_unknown_strategy_before_execution(monkeypatch):
    monkeypatch.setattr(mafft_local, "_ensure_mafft", lambda: "/fake/mafft")
    monkeypatch.setattr(
        mafft_local.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("MAFFT should not execute")),
    )
    assert mafft_local.run_local_mafft(">a\nACGT\n>b\nACGA\n", strategy="invented") is None
