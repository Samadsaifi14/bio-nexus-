from pathlib import Path

from app.ngs.stages.stage1_raw_qc_pair import raw_qc_pair_contract
from app.ngs.stages.stage3_preproc_pair import stage3_pair_contract


def _write_fastq(path: Path, mate: int) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for index in range(8):
            # Include adapter sequence in one read and low-quality tail in one read
            # so preprocessing has real work to perform without making the fixture huge.
            seq = "ACGT" * 35 + "ACGTACGTAC"
            qual = "I" * len(seq)
            if index == 0:
                seq = seq[:-13] + "AGATCGGAAGAGC"
                qual = "I" * len(seq)
            if index == 1:
                qual = "I" * 120 + "+" * (len(seq) - 120)
            handle.write(f"@read{index}/{mate}\n{seq}\n+\n{qual}\n")


def test_raw_qc_covers_both_mates(tmp_path):
    r1 = tmp_path / "sample_R1.fastq"
    r2 = tmp_path / "sample_R2.fastq"
    _write_fastq(r1, 1)
    _write_fastq(r2, 2)
    sample = {"files": [str(r1), str(r2)], "assay": "WGS", "metadata": {"read_length": 150}}
    state: dict = {}

    data, metrics = raw_qc_pair_contract().run(sample, state)

    assert data["file_count"] == 2
    assert set(data["per_file"]) == {str(r1), str(r2)}
    assert set(state["raw_qc"]) == {str(r1), str(r2)}
    assert data["total_reads"] == 16
    assert 0 <= metrics["q30"] <= 100


def test_preprocessing_writes_one_clean_fastq_per_mate_and_measures_trimmed_length(tmp_path):
    r1 = tmp_path / "sample_R1.fastq"
    r2 = tmp_path / "sample_R2.fastq"
    _write_fastq(r1, 1)
    _write_fastq(r2, 2)
    sample = {
        "files": [str(r1), str(r2)],
        "assay": "WGS",
        "metadata": {"read_length": 150, "out_dir": str(tmp_path / "work")},
        "workdir": str(tmp_path / "work"),
    }
    state: dict = {}
    raw_qc_pair_contract().run(sample, state)

    data, metrics = stage3_pair_contract().run(sample, state)

    assert data["file_count"] == 2
    assert set(state["clean_fastq"]) == {str(r1), str(r2)}
    assert all(Path(path).is_file() for path in state["clean_fastq"].values())
    assert data["retained_reads"] <= data["raw_reads"]
    assert data["avg_read_length_after"] <= 150
    assert 0 <= metrics["read_retention"] <= 100
