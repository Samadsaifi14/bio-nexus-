from __future__ import annotations

import math
from pathlib import Path

import pytest



def test_scientific_result_hash_is_deterministic():
    from app.science.result import build_scientific_result

    kwargs = dict(
        status="VALID",
        method="known-answer",
        engine="test-engine",
        engine_version="1.0",
        input_payload={"sequence": "ACGT"},
        results={"value": 4},
        parameters={"mode": "exact"},
        evidence_class="Deterministic computation",
    )
    first = build_scientific_result(**kwargs)
    second = build_scientific_result(**kwargs)
    assert first["input_sha256"] == second["input_sha256"]
    assert first["output_sha256"] == second["output_sha256"]
    assert first["results"] == {"value": 4}


def test_scientific_result_rejects_non_finite_output():
    from app.science.result import build_scientific_result

    with pytest.raises(ValueError, match="non-finite"):
        build_scientific_result(
            status="VALID",
            method="bad-number",
            engine="test",
            engine_version="1",
            input_payload="x",
            results={"value": math.nan},
        )


def _write_sam(path: Path, ref: str, reads: list[tuple[str, str]]) -> None:
    lines = ["@HD\tVN:1.6", f"@SQ\tSN:ref\tLN:{len(ref)}"]
    for index, (cigar, seq) in enumerate(reads, start=1):
        lines.append(
            f"read{index}\t0\tref\t1\t60\t{cigar}\t*\t0\t0\t{seq}\t{'I' * len(seq)}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_consensus_known_snv_is_predetermined(tmp_path: Path):
    from app.tools.sequencing import _parse_sam_evidence

    ref = "A" * 20
    read = "AAAA" + "G" + "A" * 15
    sam = tmp_path / "snv.sam"
    _write_sam(sam, ref, [("20M", read)] * 10)

    parsed = _parse_sam_evidence(
        str(sam), f">ref\n{ref}\n",
        min_depth=10,
        min_base_quality=20,
        min_mapping_quality=20,
        min_alt_freq=0.5,
        ambiguity_min_freq=0.2,
    )
    assert parsed["consensus"] == "AAAAG" + "A" * 15
    assert parsed["variants"] == [
        {
            "pos": 5,
            "ref": "A",
            "alt": "G",
            "depth": 10,
            "alt_count": 10,
            "freq": 1.0,
            "type": "SNV",
            "forward_depth": 10,
            "reverse_depth": 0,
        }
    ]


def test_consensus_masks_positions_below_minimum_depth(tmp_path: Path):
    from app.tools.sequencing import _parse_sam_evidence

    ref = "A" * 20
    sam = tmp_path / "lowdepth.sam"
    _write_sam(sam, ref, [("20M", ref)] * 9)
    parsed = _parse_sam_evidence(
        str(sam), f">ref\n{ref}\n",
        min_depth=10,
        min_base_quality=20,
        min_mapping_quality=20,
        min_alt_freq=0.5,
        ambiguity_min_freq=0.2,
    )
    assert parsed["consensus"] == "N" * 20
    assert parsed["alignment"]["callable_positions"] == 0


def test_consensus_handles_supported_insertion(tmp_path: Path):
    from app.tools.sequencing import _parse_sam_evidence

    ref = "A" * 20
    inserted_read = "AAAAA" + "G" + "A" * 15
    sam = tmp_path / "ins.sam"
    _write_sam(sam, ref, [("5M1I15M", inserted_read)] * 10)
    parsed = _parse_sam_evidence(
        str(sam), f">ref\n{ref}\n",
        min_depth=10,
        min_base_quality=20,
        min_mapping_quality=20,
        min_alt_freq=0.5,
        ambiguity_min_freq=0.2,
    )
    insertion = next(variant for variant in parsed["variants"] if variant["type"] == "INS")
    assert insertion["pos"] == 5
    assert insertion["ref"] == "A"
    assert insertion["alt"] == "AG"
    assert parsed["consensus"] == "AAAAAG" + "A" * 15


def test_historical_fallback_is_disabled():
    from app.tools.sequencing import _fallback_alignment

    with pytest.raises(RuntimeError, match="not an aligner"):
        _fallback_alignment("reads.fastq", "reference.fa", "out.sam")


@pytest.mark.asyncio
async def test_missing_minimap2_returns_degraded_and_never_consensus(monkeypatch, tmp_path: Path):
    import app.tools.sequencing as sequencing

    reference = tmp_path / "reference.fa"
    reference.write_text(">ref\n" + "ACGT" * 30 + "\n", encoding="utf-8")

    async def fake_reference(_name: str, dest_dir=None):
        return str(reference)

    async def absent_minimap2():
        raise FileNotFoundError("minimap2 deliberately removed for acceptance test")

    monkeypatch.setattr(sequencing, "_download_reference", fake_reference)
    monkeypatch.setattr(sequencing, "_ensure_minimap2", absent_minimap2)

    result = await sequencing.SequencingPipeline().run({"fastq_url": "synthetic", "reference": "sars-cov-2"})
    assert result["status"] == "DEGRADED"
    assert result["fallback_used"] is True
    assert result["results"] == {}
    assert result["validation"]["scientific_processing_stopped"] is True
    assert result["validation"]["consensus_constructed"] is False
    assert result["validation"]["no_consensus"] is True
    assert "consensus_sequence" not in result["results"]
    assert "ai_interpretation" not in result["results"]


@pytest.mark.asyncio
async def test_failed_fastq_download_is_not_replaced_by_synthetic(monkeypatch, tmp_path: Path):
    import app.tools.sequencing as sequencing

    reference = tmp_path / "reference.fa"
    reference.write_text(">ref\n" + "ACGT" * 30 + "\n", encoding="utf-8")

    async def fake_reference(_name: str, dest_dir=None):
        return str(reference)

    async def fail_fastq(_url: str, _dest: str):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(sequencing, "_download_reference", fake_reference)
    monkeypatch.setattr(sequencing, "_download_fastq", fail_fastq)

    result = await sequencing.SequencingPipeline().run({
        "fastq_url": "https://example.org/missing.fastq",
        "reference": "sars-cov-2",
    })
    assert result["status"] == "FAILED"
    assert result["results"] == {}
    assert result["validation"]["synthetic_substitution_used"] is False
