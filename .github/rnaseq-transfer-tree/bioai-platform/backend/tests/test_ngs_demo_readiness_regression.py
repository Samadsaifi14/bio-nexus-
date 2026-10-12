"""Regression tests for public NGS demo readiness."""

import os
import tempfile

from app.ngs.stages.stage0_input import run_input_validation


def _write_plain_fastq(path: str, base: str, reads: int = 12) -> None:
    seq = (base * 150)[:150]
    qual = "I" * len(seq)
    with open(path, "w", encoding="ascii") as handle:
        for i in range(reads):
            handle.write(f"@demo:{i:04d}\n{seq}\n+\n{qual}\n")


def test_plain_paired_fastq_does_not_fail_gzip_integrity():
    """Uncompressed FASTQ is valid input; gzip integrity must be N/A/PASS, not 0%."""
    with tempfile.TemporaryDirectory() as directory:
        r1 = os.path.join(directory, "BN_DEMO_WGS_R1.fastq")
        r2 = os.path.join(directory, "BN_DEMO_WGS_R2.fastq")
        _write_plain_fastq(r1, "ACGT")
        _write_plain_fastq(r2, "TGCA")

        out = run_input_validation({
            "files": [r1, r2],
            "reference": "grch38",
            "metadata": {"platform": "illumina", "read_length": 150},
        })

        assert out["summary"]["status"] == "PASS"
        assert out["summary"]["decision"] == "CONTINUE"
        validation = out["summary"]["validation"]
        assert validation["compression_summary"]["gzip_files"] == 0
        assert validation["compression_summary"]["uncompressed_files"] == 2
        assert all(item["gzip_ok"] is None for item in validation["files"])


def test_normal_r1_r2_pair_is_not_reported_as_duplicate_sample():
    with tempfile.TemporaryDirectory() as directory:
        r1 = os.path.join(directory, "SAMPLE_01_R1.fastq")
        r2 = os.path.join(directory, "SAMPLE_01_R2.fastq")
        _write_plain_fastq(r1, "ACGT")
        _write_plain_fastq(r2, "TGCA")

        out = run_input_validation({"files": [r1, r2]})
        validation = out["summary"]["validation"]
        assert "duplicate_sample_ids" not in validation
        assert not any("duplicate sample id" in message for message in validation["failures"])
