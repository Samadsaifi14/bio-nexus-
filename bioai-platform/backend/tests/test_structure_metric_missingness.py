"""Structure metrics distinguish missing evidence from a measured zero."""
import numpy as np
from app.routers.structure_analysis import _bounded_metric, _alignment_rmsd, StructureMatch


def test_bounded_metrics_preserve_zero_and_absence():
    assert _bounded_metric(0) == 0
    assert _bounded_metric(.75) == .75
    assert _bounded_metric(75, 100) == .75
    for value in (None, "bad", -1, 2, float("inf"), float("nan")):
        assert _bounded_metric(value) is None


def test_rmsd_missing_coordinates_is_not_a_perfect_match():
    assert _alignment_rmsd(b"", "A", "AAA", "AAA", 1, "") is None


def test_missing_scores_serialize_as_null():
    match = StructureMatch(pdb_id="1CRN", chain="A", description="test", tm_score=None,
        qTM=None, tTM=None, rmsd=None, seq_identity=None, aligned_length=None,
        unavailable_metrics=["tm_score","rmsd","seq_identity","aligned_length"])
    result = match.model_dump()
    assert result["tm_score"] is None
    assert result["rmsd"] is None
