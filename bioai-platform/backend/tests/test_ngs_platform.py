"""Unit tests for the NGS platform foundation: QC contract engine, assay router,
reference registry, and Stage 0 input validation."""

import gzip
import os
import tempfile

import pytest

from app.ngs.contracts import (
    Decision,
    QcStatus,
    StageContract,
    ThresholdRule,
    apply_rules,
    bounded_rule,
    decision_for,
    run_contract,
)
from app.ngs.assays import detect_assay, pair_fastq, sample_id_from_name, AssayType
from app.ngs.reference import get_reference, validate_build_compatibility, GenomeBuild
from app.ngs.stages.stage0_input import (
    probe_fastq,
    run_input_validation,
    validate_gzip,
    stage0_contract,
)


# ---------------------------------------------------------------------------
# QC contract engine
# ---------------------------------------------------------------------------


def test_bounded_rule_high_good():
    rule = bounded_rule("map", warn_min=90, ok_min=95)
    assert rule.apply(97.0).status == QcStatus.PASS
    assert rule.apply(92.0).status == QcStatus.WARN
    assert rule.apply(80.0).status == QcStatus.FAIL


def test_bounded_rule_invert_low_good():
    rule = bounded_rule("dup", warn_min=35, ok_min=10, invert=True)
    assert rule.apply(5.0).status == QcStatus.PASS
    assert rule.apply(25.0).status == QcStatus.WARN
    assert rule.apply(50.0).status == QcStatus.FAIL


def test_apply_rules_missing_metric_fails():
    rules = [bounded_rule("map", warn_min=90, ok_min=95)]
    metrics = apply_rules(rules, {})  # missing metric
    assert metrics[0].status == QcStatus.FAIL
    assert "missing" in metrics[0].detail


def test_decision_for():
    assert decision_for(QcStatus.PASS) == Decision.CONTINUE
    assert decision_for(QcStatus.WARN) == Decision.CONTINUE_WITH_WARNING
    assert decision_for(QcStatus.FAIL, fail_blocks=True) == Decision.STOP
    assert decision_for(QcStatus.FAIL, fail_blocks=False) == Decision.CONTINUE_WITH_WARNING


def test_contract_worst_aggregation():
    contract = StageContract(
        step="x", tool="t", version="1",
        inputs=["a"], outputs=["b"],
        rules=[bounded_rule("m1", warn_min=90, ok_min=95),
               bounded_rule("m2", warn_min=90, ok_min=95)],
        fail_blocks=True, run=lambda s, st: ({"d": 1}, {"m1": 96, "m2": 91}),
    )
    res = run_contract(contract, {}, {})
    assert res.qc.status == QcStatus.WARN
    assert res.decision == Decision.CONTINUE_WITH_WARNING


def test_contract_blocking_fail_stops():
    contract = StageContract(
        step="contamination", tool="t", version="1",
        inputs=["bam"], outputs=["report"],
        rules=[bounded_rule("contam", warn_min=3, ok_min=1, invert=True)],
        fail_blocks=True, run=lambda s, st: ({"d": 1}, {"contam": 8.7}),
    )
    res = run_contract(contract, {}, {})
    assert res.qc.status == QcStatus.FAIL
    assert res.decision == Decision.STOP


# ---------------------------------------------------------------------------
# Assay router
# ---------------------------------------------------------------------------


def test_pair_fastq_matches():
    pairs, singles = pair_fastq(["SAMPLE_001_R1.fastq.gz", "SAMPLE_001_R2.fastq.gz"])
    assert len(pairs) == 1
    assert pairs[0] == ("SAMPLE_001_R1.fastq.gz", "SAMPLE_001_R2.fastq.gz")
    assert not singles


def test_pair_fastq_rejects_orphan_r2():
    pairs, singles = pair_fastq(["SAMPLE_001_R2.fastq.gz"])
    assert not pairs
    assert "SAMPLE_001_R2.fastq.gz" in singles


def test_pair_fastq_rejects_mispair():
    # Different samples across R1/R2 -> they must NOT pair.
    pairs, singles = pair_fastq(["SAMPLE_001_R1.fastq.gz", "SAMPLE_002_R2.fastq.gz"])
    assert pairs == []
    assert len(singles) == 2


def test_sample_id_from_name():
    assert sample_id_from_name("SAMPLE_001_R1.fastq.gz") == "SAMPLE_001"
    assert sample_id_from_name("SAMPLE_001_R2.fastq.gz") == "SAMPLE_001"


def test_assay_rna_detection():
    det = detect_assay(files=["tumor_R1.fastq.gz", "tumor_R2.fastq.gz"], reference="GRCh38")
    assert det.detected_pairs
    assert len(det.detected_pairs) == 1


def test_assay_declared_wes():
    det = detect_assay(files=["S01_R1.fastq.gz"], metadata={"assay": "wes"})
    assert det.assay == AssayType.WES


def test_assay_amplicon_keyword():
    det = detect_assay(files=["amplicon_S1_R1.fastq.gz"])
    assert det.assay == AssayType.AMPLICON


# ---------------------------------------------------------------------------
# Reference registry
# ---------------------------------------------------------------------------


def test_reference_registry():
    ref = get_reference("grch38")
    assert ref.build == GenomeBuild.GRCH38
    names = [a.name for a in ref.artifacts]
    assert "BWA index" in names and "gnomAD" in names


def test_build_mismatch_refused():
    ok, msg = validate_build_compatibility("GRCh38", "GRCh37")
    assert not ok
    assert "PROVENANCE" in msg
    ok2, _ = validate_build_compatibility("GRCh38", "hg38")
    assert ok2


# ---------------------------------------------------------------------------
# Stage 0 input validation (helpers + full contract)
# ---------------------------------------------------------------------------


def _write_fastq(path, seq, qual="I" * 40, reads=50, gzipped=True):
    lines = []
    for i in range(reads):
        lines.append(f"@read{i} 1:N:0:1\n")
        lines.append(f"{seq}\n")
        lines.append("+\n")
        lines.append(f"{qual}\n")
    if gzipped:
        with gzip.open(path, "wt", encoding="ascii") as f:
            f.writelines(lines)
    else:
        with open(path, "w", encoding="ascii") as f:
            f.writelines(lines)
    return path


def test_probe_fastq_valid_gz():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "SAMPLE_001_R1.fastq.gz")
        _write_fastq(p, "ACGTACGT" * 5, reads=100)
        probe = probe_fastq(p)
        assert probe["records_ok"] is True
        assert probe["read_count_hint"] == 100
        assert probe["max_read_len"] == 40
        assert probe["is_gzip"] is True


def test_probe_fastq_bad_structure():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "bad.fastq.gz")
        with gzip.open(p, "wt") as f:
            f.write(">not_a_fastq_header\n")
            f.write("ACGT\n")
        probe = probe_fastq(p)
        assert probe["records_ok"] is False


def test_validate_gzip_corrupt():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "corrupt.gz")
        with open(p, "wb") as f:
            f.write(b"\x1f\x8b\x08\x00\x00\x00\x00\x00")  # header but no body -> bad
        ok, msg = validate_gzip(p)
        assert not ok


def test_stage0_full_valid_pair():
    with tempfile.TemporaryDirectory() as d:
        r1 = os.path.join(d, "SAMPLE_001_R1.fastq.gz")
        r2 = os.path.join(d, "SAMPLE_001_R2.fastq.gz")
        _write_fastq(r1, "ACGTACGT" * 5, reads=100)
        _write_fastq(r2, "TGCATGCA" * 5, reads=100)
        out = run_input_validation({
            "files": [r1, r2],
            "reference": "grch38",
            "metadata": {"assay": "wes", "platform": "illumina", "read_length": 150},
        })
        summary = out["summary"]
        assert summary["decision"] == "CONTINUE"
        assert summary["status"] == "PASS"


def test_stage0_stops_on_missing_file():
    with tempfile.TemporaryDirectory() as d:
        missing = os.path.join(d, "NOPE_R1.fastq.gz")
        out = run_input_validation({"files": [missing]})
        summary = out["summary"]
        assert summary["decision"] == "STOP"


def test_stage0_flags_mispair():
    with tempfile.TemporaryDirectory() as d:
        r1 = os.path.join(d, "SAMPLE_001_R1.fastq.gz")
        r2 = os.path.join(d, "OTHER_002_R2.fastq.gz")  # mismatched samples
        _write_fastq(r1, "ACGT" * 10, reads=20)
        _write_fastq(r2, "ACGT" * 10, reads=20)
        out = run_input_validation({"files": [r1, r2]})
        # pairing integrity fails -> STOP (mispairing is a hard input error)
        assert out["summary"]["decision"] == "STOP"
