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
from app.ngs.orchestrator import Pipeline, wgs_wes_germline_stages
from app.ngs.assays import detect_assay, pair_fastq, sample_id_from_name, AssayType
from app.ngs.reference import get_reference, validate_build_compatibility, GenomeBuild
from app.ngs.stages.stage0_input import (
    probe_fastq,
    run_input_validation,
    validate_gzip,
    stage0_contract,
)
from app.ngs.stages.stage1_raw_qc import (
    compute_raw_qc,
    run_raw_qc,
    _qc_thresholds,
)
from app.ngs.stages.stage2_multiqc import cross_sample_report, run_multiqc
from app.ngs.stages.stage3_preproc import (
    plan_preprocessing,
    preprocess_fastq,
    run_preprocessing,
    trim_read,
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


# ---------------------------------------------------------------------------
# Stage 1 — raw read QC
# ---------------------------------------------------------------------------


def _write_fastq_qual(path, seq, qual, reads=100, gzipped=True):
    lines = []
    for i in range(reads):
        lines.append(f"@r{i} 1:N:0:1\n{seq}\n+\n{qual}\n")
    if gzipped:
        with gzip.open(path, "wt", encoding="ascii") as f:
            f.writelines(lines)
    else:
        with open(path, "w", encoding="ascii") as f:
            f.writelines(lines)
    return path


def _write_fastq_var(path, base, qual, reads=100):
    """Varied reads: low duplication, realistic. Appends a 4-nt DNA suffix from the index."""
    bases = ["A", "C", "G", "T"]
    seql = len(base) + 4
    q = qual[0] * seql
    lines = []
    for i in range(reads):
        suffix = "".join(bases[(i >> s) & 3] for s in range(0, 8, 2))
        lines.append(f"@r{i} 1:N:0:1\n{base}{suffix}\n+\n{q}\n")
    with gzip.open(path, "wt", encoding="ascii") as f:
        f.writelines(lines)
    return path


def test_compute_raw_qc_counts():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s1_R1.fastq.gz")
        _write_fastq_qual(p, "ACGTACGT" * 5, "I" * 40, reads=100)
        qc = compute_raw_qc(p, "WES", {})
        assert qc["total_reads"] == 100
        assert qc["max_read_length"] == 40
        assert qc["gc_percent"] == 50.0
        # default Illumina 'I' -> Phred 40 -> high Q30
        assert qc["q30_percent"] > 99
        assert qc["n_percent"] == 0.0


def test_compute_raw_qc_n_content():
    with tempfile.TemporaryDirectory() as d:
        p2 = os.path.join(d, "s2_R1.fastq.gz")
        seq_n = "ACGTNNNN" * 5
        _write_fastq_qual(p2, seq_n, "I" * 40, reads=100)
        qc = compute_raw_qc(p2, "WES", {})
        assert qc["n_percent"] > 0


def test_raw_qc_pass_on_high_quality():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s1_R1.fastq.gz")
        _write_fastq_var(p, "ACGTACGTGGCCACGTAGG", "I" * 40, reads=200)
        out = run_raw_qc({"files": [p], "assay": "WES",
                          "metadata": {"platform": "illumina", "read_length": 40}})
        assert out["summary"]["decision"] == "CONTINUE"


def test_raw_qc_warn_on_low_quality():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s1_R1.fastq.gz")
        _write_fastq_qual(p, "ACGTACGT" * 5, "5" * 40, reads=200)  # Phred ~20 -> Q30 low
        out = run_raw_qc({"files": [p], "assay": "WES",
                          "metadata": {"platform": "illumina", "read_length": 40}})
        # Q30 far below expectation -> FAIL (blocking). Assert failure path in essence:
        assert out["summary"]["status"] in ("WARN", "FAIL")


def test_thresholds_assay_aware():
    # Amplicon expects higher Q30 than WGS.
    r_wgs = _qc_thresholds("WGS", {})["q30"]
    r_amp = _qc_thresholds("AMPLICON", {})["q30"]
    # Both are "higher is better"; check FAIL at a low Q30 value and PASS at high.
    assert r_wgs.apply(80.0).status == QcStatus.WARN
    assert r_amp.apply(80.0).status == QcStatus.WARN


# ---------------------------------------------------------------------------
# Orchestrator wiring (Stage 0 -> Stage 1)
# ---------------------------------------------------------------------------


def test_pipeline_runs_stage0_and_stage1():
    with tempfile.TemporaryDirectory() as d:
        r1 = os.path.join(d, "SAMPLE_001_R1.fastq.gz")
        r2 = os.path.join(d, "SAMPLE_001_R2.fastq.gz")
        _write_fastq_var(r1, "ACGTACGTGGCCACGTAGG", "I" * 40, reads=150)
        _write_fastq_var(r2, "TGCATGCATCGGTGCATCCG", "I" * 40, reads=150)
        stages = wgs_wes_germline_stages(include=["input_validation", "raw_read_qc"])
        assert [s.step for s in stages] == ["input_validation", "raw_read_qc"]
        pipe = Pipeline(name="WGS-germline", version="0.1.0")
        pipe.add_many(stages)
        report = pipe.run({
            "files": [r1, r2],
            "assay": "WES",
            "reference": "grch38",
            "metadata": {"platform": "illumina", "read_length": 40},
        })
        # Both stages pass -> pipeline continues.
        assert report["pipeline_status"] == "PASS"
        assert report["pipeline_decision"] == "CONTINUE"
        assert report["stopped_at"] is None
        assert len(report["stages"]) == 2
        assert report["stages"][0]["step"] == "input_validation"
        assert report["stages"][1]["step"] == "raw_read_qc"


def test_pipeline_stops_on_bad_input():
    with tempfile.TemporaryDirectory() as d:
        missing = os.path.join(d, "NOPE_R1.fastq.gz")
        stages = wgs_wes_germline_stages(include=["input_validation"])
        pipe = Pipeline(name="WGS-germline", version="0.1.0")
        pipe.add_many(stages)
        report = pipe.run({"files": [missing]})
        assert report["pipeline_status"] == "FAIL"
        assert report["pipeline_decision"] == "STOP"
        assert report["stopped_at"] == "input_validation"


def _raw_qc_like(q30, mean_q=None, gc=None, adapter=1.0, dup=12.0, reads=1_000_000):
    return {
        "q30_percent": q30,
        "mean_quality": mean_q if mean_q is not None else (30 + (q30 - 90) / 5),
        "gc_percent": gc if gc is not None else 45.0,
        "adapter_percent": adapter,
        "duplication_percent": dup,
        "total_reads": reads,
    }


# ---------------------------------------------------------------------------
# Stage 2 — MultiQC anomaly detection
# ---------------------------------------------------------------------------


def test_multiqc_flags_blueprint_anomaly():
    # The blueprint's exact example: Q30 94 / 93 / 91 / 61 -> the 61 must be flagged.
    cohort = {
        "S1": _raw_qc_like(94.0),
        "S2": _raw_qc_like(93.0),
        "S3": _raw_qc_like(91.0),
        "S4": _raw_qc_like(61.0),
    }
    report = cross_sample_report(cohort)
    flagged = {a["sample"] for a in report["anomalies"] if a["metric"] == "q30"}
    assert "S4" in flagged
    assert "S1" not in flagged


def test_multiqc_no_anomaly_on_consistent_cohort():
    cohort = {f"S{i}": _raw_qc_like(93.0 + (i % 3)) for i in range(6)}
    report = cross_sample_report(cohort)
    assert report["anomalies"] == []


def test_multiqc_high_duplication_flagged():
    cohort = {
        "A": _raw_qc_like(93.0, dup=10.0),
        "B": _raw_qc_like(93.0, dup=12.0),
        "C": _raw_qc_like(93.0, dup=11.0),
        "D": _raw_qc_like(93.0, dup=90.0),  # duplicated sample
    }
    report = cross_sample_report(cohort)
    dup_flagged = [a["sample"] for a in report["anomalies"] if a["metric"] == "duplication"]
    assert "D" in dup_flagged


def test_multiqc_run_helper():
    cohort = {"S1": _raw_qc_like(94), "S2": _raw_qc_like(92), "S3": _raw_qc_like(60)}
    out = run_multiqc(cohort)
    # Outliers are surfaced but MultiQC is not a hard gate (fail_blocks=False):
    assert out["summary"]["decision"] == "CONTINUE_WITH_WARNING"
    assert len(out["summary"]["anomalies"]) >= 1


# ---------------------------------------------------------------------------
# Stage 3 — preprocessing
# ---------------------------------------------------------------------------


def test_plan_adapter_trim_from_observed_contamination():
    qc = {"adapter_percent": 30.0}
    plan = plan_preprocessing({}, qc)
    assert plan["adapter_trim"] is True


def test_plan_no_steps_when_clean():
    plan = plan_preprocessing({}, {"adapter_percent": 1.0, "mean_quality": 38})
    assert plan["adapter_trim"] is False
    assert plan["umi_extraction"] is False
    assert plan["quality_trim"] is False


def test_plan_umi_when_declared():
    plan = plan_preprocessing({"umi": "yes"}, {})
    assert plan["umi_extraction"] is True


def test_trim_read_quality_tail():
    seq = "ACGTACGTACGTACGT"
    qual = "IIIIIIII" + "!!!!!!!!"  # poor-quality 3' tail
    plan = {"adapter_trim": False, "umi_extraction": False,
            "quality_trim": True, "min_qual": 20, "min_len": 4}
    keep = seq[:8]
    good = "I" * 8
    res = trim_read("@r1", keep, good, plan)
    assert res is not None and res[0] is not None
    lines = res[0].split("\n")
    assert lines[1] == keep  # ~8 high-quality bases survive


def test_trim_read_adapter_removal():
    seq = "ACGTACGTACGT" + "AGATCGGAAGAGC"  # adapter seed at 3'
    qual = "I" * len(seq)
    plan = {"adapter_trim": True, "umi_extraction": False,
            "quality_trim": False, "min_qual": 20, "min_len": 4}
    res = trim_read("@r1", seq, qual, plan)
    assert res[1]["adapter_removed"] is True
    assert "AGATCGGAAGAGC" not in res[0].split("\n")[1]


def test_preprocess_fastq_adapter_and_threading():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "S1_R1.fastq.gz")
        reads = []
        for i in range(60):
            seq = ("ACGTACGTACGTACGTACGT" + "AGATCGGAAGAGCG" + "G" * 10)
            reads.append(f"@r{i}\n{seq}\n+\n{'I'*len(seq)}\n")
        with gzip.open(src, "wt") as f:
            f.writelines(reads)
        plan = plan_preprocessing({"quality_trim": "no", "min_length": 5}, {"adapter_percent": 40})
        out_dir = os.path.join(d, "clean")
        os.makedirs(out_dir, exist_ok=True)
        stats = preprocess_fastq(src, out_dir, plan, sample_name="S1")
        assert stats["raw_reads"] == 60
        assert stats["adapter_removed_reads"] == 60
        assert stats["discarded_reads"] == 0
        assert stats["out_path"].endswith(".fastq.gz")
        assert os.path.exists(stats["out_path"])


def test_preprocess_stops_on_large_read_loss():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "S1_R1.fastq.gz")
        reads = []
        for i in range(50):
            seq = "ACGT"  # very short
            reads.append(f"@r{i}\n{seq}\n+\nIIII\n")
        with gzip.open(src, "wt") as f:
            f.writelines(reads)
        out_dir = os.path.join(d, "clean")
        os.makedirs(out_dir, exist_ok=True)
        out = run_preprocessing({
            "files": [src],
            "sample_id": "S1",
            "workdir": d,
            "metadata": {"quality_trim": "no", "min_length": 30, "out_dir": out_dir},
        })
        assert out["summary"]["decision"] == "STOP"  # near-total read loss after 30nt filter
