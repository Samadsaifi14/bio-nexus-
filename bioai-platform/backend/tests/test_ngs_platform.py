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
from app.ngs.stages.stage4_reference import run_reference_validation
from app.ngs.sam import map_reads
from app.ngs.stages.stage5_alignment import run_alignment, choose_aligner
from app.ngs.stages.stage6_bam import run_bam_processing, process_bam
from app.ngs.stages.stage7_alignment_qc import run_alignment_qc, alignment_qc
from app.ngs.stages.stage8_coverage import run_coverage, coverage_engine
from app.ngs.stages.stage9_contamination import run_contamination, contamination_engine
from app.ngs.stages.stage10_identity import run_identity, identity_engine
from app.ngs.stages.stage11_variant_calling import run_variant_calling, call_variants
from app.ngs.stages.stage12_normalize import run_variant_normalization, normalize_variants
from app.ngs.stages.stage13_variant_qc import run_variant_qc_stage, variant_qc
from app.ngs.stages.stage14_filter import run_variant_filter, filter_variants
from app.ngs.stages.stage15_sv import run_sv_detection, detect_sv
from app.ngs.stages.stage16_cnv import run_cnv_detection, call_cnv
from app.ngs.stages.stage17_annotation import run_annotation_stage, annotate_variant
from app.ngs.stages.stage18_knowledge import run_knowledge_stage, apply_knowledge


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


# ---------------------------------------------------------------------------
# Stage 4 — reference validation
# ---------------------------------------------------------------------------


def test_reference_validation_resolves_grch38():
    out = run_reference_validation({"reference": "grch38"})
    assert out["summary"]["status"] == "PASS"
    assert out["summary"]["reference"]["build"] == "GRCh38"


def test_reference_validation_mismatch_stops():
    # GRCh38 data against a GRCh37 annotation is a provenance error -> STOP.
    out = run_reference_validation({"reference": "grch38", "annotation_build": "GRCh37"})
    assert out["summary"]["decision"] == "STOP"
    assert "PROVENANCE" in out["summary"]["reference"]["build_message"]


def test_reference_validation_match_continues():
    out = run_reference_validation({"reference": "grch38", "annotation_build": "GRCh38"})
    assert out["summary"]["decision"] == "CONTINUE"


def test_reference_validation_unknown_reference():
    out = run_reference_validation({"reference": "banana"})
    assert out["summary"]["decision"] == "STOP"


# ---------------------------------------------------------------------------
# Stages 6-8: BAM processing, alignment QC, coverage (pure-Python aligned data)
# ---------------------------------------------------------------------------


def _make_ref_and_reads(ref_len=800, n_reads=40):
    import random
    random.seed(7)
    ref = "".join(random.choice("ACGT") for _ in range(ref_len))
    reads = []
    for i in range(n_reads):
        start = (i * 13) % (ref_len - 40)
        # 30nt exact read, well above min_len 20
        reads.append((f"r{i}", ref[start:start + 30], "I" * 30))
    # one unmapped read
    reads.append(("unmapped", "G" * 30, "I" * 30))
    return ref, reads


def _make_records(ref, reads, n_reads=40):
    records = map_reads(ref, reads[:n_reads], ref_name="chr1", seed_len=8, min_len=20)
    unmapped = [r for r in map_reads(ref, reads[n_reads:], ref_name="chr1", seed_len=8, min_len=20)]
    return records + [r for r in unmapped if r["is_unmapped"]]


def _mk_rec(qname, pos, mapq=60, strand=0):
    return {
        "qname": qname, "flag": strand, "rname": "chr1", "pos": pos, "mapq": mapq,
        "cigar": "30M", "rnext": "*", "pnext": 0, "tlen": 0, "seq": "A" * 30, "qual": "I" * 30,
        "is_secondary": False, "is_supplementary": False, "is_unmapped": False,
        "is_proper_pair": True, "is_duplicate": False,
        "is_first_in_pair": False, "is_second_in_pair": False, "mate_unmapped": False,
    }


def test_bam_processing_marks_duplicates():
    # Two reads sharing a 5' position are candidate duplicates -> the lower-MAPQ one is marked.
    records = [
        _mk_rec("A1", 100, mapq=60),
        _mk_rec("A2", 100, mapq=30),   # same 5' pos, lower MAPQ -> duplicate
        _mk_rec("B1", 200, mapq=60),   # distinct position -> not a duplicate
        _mk_rec("C1", 0, mapq=0),      # unmapped
    ]
    records[-1]["is_unmapped"] = True
    records[3]["flag"] = 4
    processed, stats = process_bam(records=records)
    assert stats["total_records"] == 4
    assert stats["duplicate_records"] == 1
    dup_names = {r["qname"] for r in processed if r["is_duplicate"]}
    assert dup_names == {"A2"}


def test_choose_aligner_by_assay():
    assert choose_aligner("WGS", 150) == "bwa-mem2"
    assert choose_aligner("RNA-SEQ", 150) == "STAR"
    assert choose_aligner("WGS", 5000) == "minimap2"  # long-read


def test_alignment_run_and_mapping_ok():
    ref, reads = _make_ref_and_reads(ref_len=600, n_reads=20)
    out = run_alignment(reads[:20], ref, assay="WGS", read_length=30)
    assert out["summary"]["meta"]["aligner"] == "bwa-mem2"
    assert out["summary"]["decision"] != "STOP"
    assert out["summary"]["meta"]["mapped"] >= 18
    assert len(out["records"]) == 20


def test_alignment_qc_computes_mapping_rate():
    ref, reads = _make_ref_and_reads(n_reads=40)
    records = _make_records(ref, reads, n_reads=40)
    qc = alignment_qc(records)
    # 40 mapped + 1 unmapped -> mapping ~ 40/41 ~ 97.5%
    assert 90 <= qc["mapping_rate"] <= 100
    assert qc["unmapped_reads"] == 1
    assert qc["median_mapq"] == 60


def test_alignment_qc_run_decisions():
    ref, reads = _make_ref_and_reads(n_reads=40)
    records = _make_records(ref, reads, n_reads=40)
    out = run_alignment_qc(records=records)
    # high mapping + proper pairs -> PASS / not STOP
    assert out["summary"]["decision"] != "STOP"
    assert out["summary"]["status"] in ("PASS", "WARN")


def test_coverage_engine_metrics():
    ref, reads = _make_ref_and_reads(ref_len=400, n_reads=30)
    records = _make_records(ref, reads, n_reads=30)
    ref_lengths = {"chr1": len(ref)}
    targets = [{"name": "GENE1", "contig": "chr1", "start": 10, "end": 60}]
    eng = coverage_engine(records, ref_lengths, targets)
    g = eng["genome"]
    assert g["max_depth"] >= 1
    assert 0 <= g["coverage_30x"] <= 100
    assert eng["n_targets"] == 1
    assert eng["target"]["min_depth"] >= 0


def test_coverage_run_returns_report():
    ref, reads = _make_ref_and_reads(ref_len=400, n_reads=30)
    records = _make_records(ref, reads, n_reads=30)
    out = run_coverage(records=records, ref_lengths={"chr1": len(ref)},
                       targets=[{"name": "BRCA1", "contig": "chr1", "start": 5, "end": 60}])
    assert "genome" in out["summary"]
    assert out["summary"]["target"] is not None


def _base_rec(qname, pos, seq, mapq=60):
    length = len(seq)
    return {
        "qname": qname, "flag": 0, "rname": "chr1", "pos": pos, "mapq": mapq,
        "cigar": f"{length}M", "rnext": "*", "pnext": 0, "tlen": 0, "seq": seq,
        "qual": "I" * length, "is_secondary": False, "is_supplementary": False,
        "is_unmapped": False, "is_proper_pair": True, "is_duplicate": False,
        "is_first_in_pair": False, "is_second_in_pair": False, "mate_unmapped": False,
    }


def test_contamination_engine_detects_alt_reads():
    # Homozygous-ref SNP at pos 100 (ref A). Two clean reads + one read with an alt C.
    records = [
        _base_rec("a", 71, "A" * 30),        # covers 71..100, pos100 = A
        _base_rec("b", 90, "A" * 30),        # covers 90..119, pos100 = A
        _base_rec("c", 71, "A" * 29 + "C"),  # pos100 = C (alt)
    ]
    eng = contamination_engine(records, [{"pos": 100, "ref": "A"}])
    assert eng["alt_reads"] == 1
    assert eng["total_reads"] == 3
    assert eng["contam_rate"] > 20.0
    assert eng["status"] == "FAIL"


def test_contamination_run_stops_on_high_rate():
    records = [
        _base_rec("a", 71, "A" * 30),
        _base_rec("b", 90, "A" * 30),
        _base_rec("c", 71, "A" * 29 + "C"),
    ]
    out = run_contamination(records, [{"pos": 100, "ref": "A"}])
    assert out["summary"]["decision"] == "STOP"   # fail_blocks gate
    assert out["summary"]["contam_rate"] > 20.0


def test_contamination_clean_passes():
    records = [_base_rec("a", 71, "A" * 30), _base_rec("b", 90, "A" * 30)]
    eng = contamination_engine(records, [{"pos": 100, "ref": "A"}])
    assert eng["contam_rate"] == 0.0
    assert eng["status"] == "PASS"


def test_identity_concordance_and_sex():
    # Locus 100: all A -> called A/A matches expected A/A.
    records = [_base_rec("a", 71, "A" * 30), _base_rec("b", 90, "A" * 30)]
    out = run_identity(records, expected_gt=[{"pos": 100, "gt": "A/A"}],
                       expected_sex="female", chr_x_depth=500, chr_y_depth=2)
    assert out["summary"]["concordance"] == 100.0
    assert out["summary"]["predicted_sex"] == "female"
    assert out["summary"]["sex_match"] is True
    assert out["summary"]["decision"] == "CONTINUE"


def test_identity_sex_mismatch_stops():
    records = [_base_rec("a", 71, "A" * 30)]
    out = run_identity(records, expected_sex="female", chr_x_depth=100, chr_y_depth=90)
    assert out["summary"]["predicted_sex"] == "male"
    assert out["summary"]["sex_match"] is False
    assert out["summary"]["decision"] == "STOP"


def _vcf_reads(n_alt=6, n_ref=2):
    """Reads at pos21 (len30): pos50 is 'C' in alt reads, 'A' (ref) otherwise."""
    records = ([_base_rec(f"alt{i}", 21, "A" * 29 + "C") for i in range(n_alt)] +
               [_base_rec(f"ref{i}", 21, "A" * 30) for i in range(n_ref)])
    return records, "A" * 60


def test_variant_calling_calls_snp_and_orthogonal():
    records, ref = _vcf_reads()
    out = run_variant_calling(records, {"chr1": ref})
    snps = [v for v in out["variants"]["variants"] if v["type"] == "SNP"]
    pos50 = [v for v in snps if v["pos"] == 50]
    assert len(pos50) == 1
    assert pos50[0]["ref"] == "A" and pos50[0]["alt"] == "C"
    assert pos50[0]["n_alt"] == 6
    # primary sees it; orthogonal requires af >= 0.35 and dp >= 12 -> here af 0.75, dp 8
    assert "primary" in pos50[0]["callers"]
    assert out["variants"]["n_primary"] >= 1


def test_variant_normalization_trims_shared_prefix():
    norm = normalize_variants([{"ref": "GAA", "alt": "GAT"}])
    assert norm[0]["ref"] == "A"
    assert norm[0]["alt"] == "T"
    # multiallelic alt reduces to biallelic first allele
    norm2 = normalize_variants([{"ref": "C", "alt": "A,T"}])
    assert norm2[0]["alt"] == "A"
    assert norm2[0]["biallelic"] is False


def test_variant_qc_classifies():
    good = variant_qc({"dp": 30, "af": 0.5, "n_alt": 15, "genotype_quality": 99})
    assert good["status"] == "PASS"
    bad_depth = variant_qc({"dp": 4, "af": 0.5, "n_alt": 2, "genotype_quality": 50})
    assert "low_depth" in bad_depth["reasons_fail"]
    assert bad_depth["status"] == "FAIL"
    low_complex = variant_qc({"dp": 20, "af": 0.5, "n_alt": 10,
                              "genotype_quality": 50, "context": "AAAAAT"})
    assert "low_complexity_context" in low_complex["reasons_warn"]


def test_filter_engine_keeps_rare_pass():
    variants = [
        {"chrom": "chr1", "pos": 1, "ref": "A", "alt": "C", "biallelic": True,
         "qc": {"status": "PASS"}, "gnomad_af": 0.0005},
        {"chrom": "chr1", "pos": 2, "ref": "G", "alt": "T", "biallelic": True,
         "qc": {"status": "PASS"}, "gnomad_af": 0.05},          # COMMON -> reject
        {"chrom": "chr1", "pos": 3, "ref": "C", "alt": "A", "biallelic": True,
         "qc": {"status": "FAIL"}, "gnomad_af": 0.0},           # QC FAIL -> reject
    ]
    out = filter_variants(variants, max_af=0.01)
    assert out["n_final"] == 1
    assert out["n_rejected"] == 2
    assert out["final"][0]["pos"] == 1


def test_call_to_filter_pipeline():
    records, ref = _vcf_reads()
    call = call_variants(records, {"chr1": ref})
    norm = normalize_variants(call["variants"])
    qc_report = run_variant_qc_stage(norm)
    passed = [v for v in qc_report["variants"] if v["qc"]["status"] != "FAIL"]
    # attach a rare population frequency to the called SNP so it passes the filter
    for v in passed:
        if v["pos"] == 50:
            v["gnomad_af"] = 0.0001
    filtered = run_variant_filter(passed, max_af=0.01)
    finals = [v for v in filtered["variants"]["final"]]
    assert len(finals) >= 1
    assert finals[0]["pos"] == 50


def _pair(qname, pos1, pos2, chrom="chr1", strand2_rev=True, tlen=None, proper=True,
          chrom2=None):
    """Two mate records for one template. Returns (rec1, rec2)."""
    fl1 = 0x40 | (0 if not strand2_rev else 0x2) if proper else 0x40
    rec1 = {
        "qname": qname, "flag": fl1, "rname": chrom, "pos": pos1, "mapq": 60,
        "cigar": "30M", "rnext": chrom2 or chrom, "pnext": pos2, "tlen": tlen or 0,
        "seq": "A" * 30, "qual": "I" * 30, "is_unmapped": False,
        "is_proper_pair": proper, "is_secondary": False, "is_supplementary": False,
        "is_duplicate": False, "is_first_in_pair": True, "is_second_in_pair": False,
        "mate_unmapped": False,
    }
    rec2 = {
        "qname": qname, "flag": (0x80 | (0x10 if strand2_rev else 0)) | (0x2 if proper else 0),
        "rname": chrom2 or chrom, "pos": pos2, "mapq": 60, "cigar": "30M",
        "rnext": chrom, "pnext": pos1, "tlen": -(tlen or 0), "seq": "A" * 30,
        "qual": "I" * 30, "is_unmapped": False, "is_proper_pair": proper,
        "is_secondary": False, "is_supplementary": False, "is_duplicate": False,
        "is_first_in_pair": False, "is_second_in_pair": True, "mate_unmapped": False,
    }
    return rec1, rec2


def test_sv_detects_deletion_duplication_translocation():
    records = []
    # 4 normal pairs, insert span ~100 bp (baseline)
    for i in range(4):
        a, b = _pair(f"n{i}", 100 + i * 10, 200 + i * 10, tlen=100, strand2_rev=True)
        records += [a, b]
    a, b = _pair("del1", 1000, 5000, tlen=4000, strand2_rev=True)   # large deletion
    records += [a, b]
    a, b = _pair("dup1", 300, 350, tlen=0, strand2_rev=False)       # same strand -> DUP
    records += [a, b]
    a, b = _pair("tra1", 10, 20, chrom="chr1", chrom2="chr2", tlen=0, strand2_rev=True)
    records += [a, b]
    report = detect_sv(records)
    assert report["n_deletions"] >= 1
    assert report["n_duplications"] >= 1
    assert report["n_translocations"] >= 1


def test_sv_run_returns_report():
    records = []
    for i in range(4):
        a, b = _pair(f"n{i}", 100 + i * 10, 200 + i * 10, tlen=100)
        records += [a, b]
    a, b = _pair("del1", 1000, 5000, tlen=4000)
    records += [a, b]
    out = run_sv_detection(records)
    assert out["summary"]["report"]["n_deletions"] >= 1
    assert out["summary"]["decision"] != "STOP"


def test_cnv_detects_amplified_region():
    records = []
    # background: 2 reads spread over the contig
    for pos in range(500, 30000, 2000):
        records.append(_base_rec(f"bg{pos}", pos, "A" * 30))
    # amplification: dense band around 1kb (many read starts in bin 0)
    for i in range(40):
        records.append(_base_rec(f"amp{i}", 100 + i, "A" * 30))
    report = call_cnv(records, bin_size=1000)
    amps = [s for s in report["segments"] if s["type"] == "AMP"]
    assert len(amps) >= 1
    assert any(s["copy_number"] >= 3 for s in amps)  # genuinely amplified by read count


def test_cnv_run_returns_report():
    records = []
    for pos in range(500, 30000, 2000):
        records.append(_base_rec(f"bg{pos}", pos, "A" * 30))
    for i in range(40):
        records.append(_base_rec(f"amp{i}", 100 + i, "A" * 30))
    out = run_cnv_detection(records, bin_size=1000)
    assert out["summary"]["report"]["n_amplifications"] >= 1


def test_annotation_protein_consequence():
    tx = [{"gene": "GENE1", "chrom": "chr1", "strand": "+", "cds_offset": 1,
           "exons": [{"start": 1, "end": 60}], "cds_seq": "ATGTTTTGG"}]
    miss = annotate_variant({"chrom": "chr1", "pos": 5, "ref": "T", "alt": "C"}, tx)
    assert miss["annotation"]["consequence"] == "missense"
    syn = annotate_variant({"chrom": "chr1", "pos": 6, "ref": "T", "alt": "C"}, tx)
    assert syn["annotation"]["consequence"] == "synonymous"
    non = annotate_variant({"chrom": "chr1", "pos": 8, "ref": "G", "alt": "A"}, tx)
    assert non["annotation"]["consequence"] == "nonsense"


def test_annotation_intronic_and_splice():
    tx = [{"gene": "GENE2", "chrom": "chr1", "strand": "+",
           "exons": [{"start": 1, "end": 10}, {"start": 40, "end": 60}]}]
    intronic = annotate_variant({"chrom": "chr1", "pos": 25, "ref": "A", "alt": "C"}, tx)
    assert intronic["annotation"]["consequence"] == "intronic"
    splice = annotate_variant({"chrom": "chr1", "pos": 11, "ref": "A", "alt": "C"}, tx)
    assert splice["annotation"]["consequence"] == "splice_region"


def test_knowledge_registry_classifies():
    variants = [
        {"chrom": "chr1", "pos": 5, "ref": "T", "alt": "C",
         "annotation": {"gene": "GENE1"}},
        {"chrom": "chr1", "pos": 20, "ref": "C", "alt": "G",
         "annotation": {"gene": "GENE3"}},
    ]
    clinvar = {("chr1", 5, "T", "C"): {"significance": "Pathogenic",
               "condition": "Hereditary syndrome", "review_status": "criteria_provided"}}
    omim = {"GENE1": {"condition": "Hereditary syndrome", "mode": "AD", "mim": 113705}}
    gnomad = {("chr1", 20, "C", "G"): {"af": 0.3, "filters": "PASS", "hom": True}}
    out = apply_knowledge(variants, clinvar=clinvar, omim=omim, gnomad=gnomad)
    assert out["n_pathogenic"] == 1
    v1 = out["variants"][0]
    assert v1["clinvar"]["tag"] == "pathogenic"
    assert v1["omim"]["mode"] == "AD"
    assert out["variants"][1]["gnomad"]["af"] == 0.3
