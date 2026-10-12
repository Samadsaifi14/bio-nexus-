from pathlib import Path

from app.ngs.orchestrator import build_dag, rna_seq_preview_stages
from app.ngs.stages.stage3_preproc_pair import run_preprocessing_pair


def _write_fastq(path: Path, mate: int) -> None:
    with path.open("w", encoding="ascii") as handle:
        for index in range(4):
            sequence = ("ACGT" * 38)[:150]
            quality = "I" * 120 + "+" * 30 if index == 0 else "I" * 150
            handle.write(f"@GUIDED:{index:03d}/{mate}\n{sequence}\n+\n{quality}\n")


def test_rna_preview_includes_preprocessing_before_expression_boundary():
    steps = [contract.step for contract in rna_seq_preview_stages()]
    assert steps == [
        "input_validation",
        "raw_read_qc",
        "multiqc",
        "preprocessing",
        "rna_read_summary",
        "rna_production_boundary",
    ]
    pipeline = build_dag("RNA-seq")
    assert pipeline.version == "0.4.0"


def test_preprocessing_emits_authentic_before_after_sequence_examples(tmp_path: Path):
    r1 = tmp_path / "sample_R1.fastq"
    r2 = tmp_path / "sample_R2.fastq"
    _write_fastq(r1, 1)
    _write_fastq(r2, 2)

    result = run_preprocessing_pair({
        "files": [str(r1), str(r2)],
        "assay": "RNA-SEQ",
        "metadata": {"out_dir": str(tmp_path / "out")},
    })

    assert result["summary"]["status"] in {"PASS", "WARN"}
    per_file = result["summary"]["stats"]["per_file"]
    assert set(per_file) == {str(r1), str(r2)}
    for item in per_file.values():
        examples = item["trim_examples"]
        assert examples
        assert examples[0]["before_length"] == len(examples[0]["before"])
        assert examples[0]["after_length"] == len(examples[0]["after"])
        assert examples[0]["removed_bases"] >= 0
