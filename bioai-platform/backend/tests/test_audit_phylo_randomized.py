"""Publication audit for local phylogenetic helpers and request provenance.

Network MSA/ML execution is validated separately. These checks focus on local
p-distance/UPGMA behaviour, taxon preservation, input validation, and the
requested-versus-effective ML bootstrap contract.
"""

from __future__ import annotations

import random

import pytest
from Bio import Phylo
from io import StringIO

from app.routers.phylo import (
    PhyloRequest,
    _p_distance,
    _parse_aligned_fasta,
    _upgma_newick,
    fasta_to_phylip,
    _validate_sequence_records,
    _resolve_ml_model,
    _effective_iqtree_bootstrap,
)


SEED = 20260916


def test_random_p_distance_matches_independent_definition():
    rng = random.Random(SEED)
    alphabet = "ACGT-"
    for _ in range(200):
        a = "".join(rng.choice(alphabet) for _ in range(rng.randint(5, 120)))
        b = "".join(rng.choice(alphabet) for _ in range(len(a)))
        comparable = [(x, y) for x, y in zip(a, b) if x != "-" and y != "-"]
        expected = 1.0 if not comparable else sum(x != y for x, y in comparable) / len(comparable)
        assert _p_distance(a, b) == pytest.approx(expected, abs=1e-12)


def test_seeded_upgma_preserves_every_unique_taxon_once_and_emits_parseable_newick():
    rng = random.Random(SEED + 1)
    for replicate in range(50):
        taxa = [f"taxon_{replicate}_{i}" for i in range(rng.randint(2, 12))]
        seqs = {name: "".join(rng.choice("ACGT") for _ in range(40)) for name in taxa}
        fasta = "\n".join(f">{name}\n{seq}" for name, seq in seqs.items())
        newick = _upgma_newick(fasta)
        tree = Phylo.read(StringIO(newick), "newick")
        leaves = [leaf.name for leaf in tree.get_terminals()]
        assert sorted(leaves) == sorted(taxa)
        assert len(leaves) == len(set(leaves)) == len(taxa)
        assert all((clade.branch_length or 0.0) >= 0.0 for clade in tree.find_clades())


def test_aligned_fasta_rejects_duplicate_taxon_ids_instead_of_overwriting():
    duplicate = ">sample\nAAAA\n>sample\nAAAT\n"
    with pytest.raises(ValueError, match="Duplicate"):
        _parse_aligned_fasta(duplicate)


def test_phylip_conversion_rejects_unequal_alignment_lengths():
    bad = ">a\nAAAA\n>b\nAAA\n"
    with pytest.raises(ValueError, match="same aligned length"):
        fasta_to_phylip(bad)


def test_sequence_record_validation_rejects_missing_duplicate_and_wrong_alphabet():
    with pytest.raises(ValueError):
        _validate_sequence_records([{"id": "a", "sequence": "AAAA"}, {"id": "a", "sequence": "AAAT"}], "dna")
    with pytest.raises(ValueError):
        _validate_sequence_records([{"id": "a", "sequence": ""}, {"id": "b", "sequence": "AAAA"}], "dna")
    with pytest.raises(ValueError):
        _validate_sequence_records([{"id": "a", "sequence": "MKWV"}, {"id": "b", "sequence": "MKWV"}], "dna")
    with pytest.raises(ValueError):
        _validate_sequence_records([{"id": "a", "sequence": "ATGC"}, {"id": "b", "sequence": "ATGC"}], "protein")


def test_sequence_record_validation_accepts_iupac_dna_and_standard_protein():
    dna = _validate_sequence_records(
        [{"id": "a", "sequence": "ACGTRYSWKMBDHVN"}, {"id": "b", "sequence": "ACGTNNNNNNNNNNN"}],
        "dna",
    )
    assert [x["id"] for x in dna] == ["a", "b"]
    protein = _validate_sequence_records(
        [{"id": "p1", "sequence": "MKWVTFISLL"}, {"id": "p2", "sequence": "MKWVTFISLI"}],
        "protein",
    )
    assert len(protein) == 2


def test_ml_default_model_depends_on_sequence_type():
    assert _resolve_ml_model(None, "protein") == "LG"
    assert _resolve_ml_model(None, "dna") == "GTR"
    with pytest.raises(ValueError):
        _resolve_ml_model("LG", "dna")
    with pytest.raises(ValueError):
        _resolve_ml_model("GTR", "protein")


def test_iqtree_effective_bootstrap_is_recorded_truthfully():
    assert _effective_iqtree_bootstrap(0) == 0
    assert _effective_iqtree_bootstrap(1) == 1000
    assert _effective_iqtree_bootstrap(100) == 1000
    assert _effective_iqtree_bootstrap(999) == 1000
    assert _effective_iqtree_bootstrap(1000) == 1000
    assert _effective_iqtree_bootstrap(1500) == 1500


def test_request_model_can_be_omitted_for_both_sequence_types():
    protein_req = PhyloRequest(sequences=[{"id": "a", "sequence": "MKWV"}, {"id": "b", "sequence": "MKWI"}], method="ml", seq_type="protein")
    dna_req = PhyloRequest(sequences=[{"id": "a", "sequence": "ATGC"}, {"id": "b", "sequence": "ATGT"}], method="ml", seq_type="dna")
    assert protein_req.model is None
    assert dna_req.model is None
