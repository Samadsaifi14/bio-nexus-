"""Deterministic consensus-sequencing tests: known reference + SNVs, deletions,
low-coverage N-masking, DEGRADED hard-stop, and ScientificResult contract output.

Uses hand-crafted SAM records with fully determined pileup so there is no
dependence on minimap2 (or any network) being available.
"""

import asyncio
import pytest

from app.tools.sequencing import SequencingPipeline, _build_consensus, _pileup_reads

# Reference layout (AST-verified via enumerate): G5 A4 C5 T5 G5 A4 C5 T5 = 38 nt.
REF = "GGGGGAAAACCCCCTTTTTGGGGGAAAACCCCCTTTTT"

# 0-based mutation map applied to all "mutant" reads.
SNVS = {11: "A", 26: "G", 37: "C"}
DEL_POS = 17  # 0-based; 1-based position 18.


def _qual(seq: str) -> str:
    return "".join(chr(33 + 30) for _ in seq)


def _sam_read(name: str, cigar: str, seq: str, flag: int = 0, mapq: int = 60) -> str:
    return f"{name}\t{flag}\tchr1\t1\t{mapq}\t{cigar}\t*\t0\t0\t{seq}\t{_qual(seq)}"


def _read_seq(span_end: int, with_del: bool, mutations: dict[int, str]) -> str:
    """Reference-derived read covering 0..span_end, optional deletion at DEL_POS."""
    bases = []
    for i, b in enumerate(REF):
        if i >= span_end:
            break
        if with_del and i == DEL_POS:
            continue
        bases.append(mutations.get(i, b))
    return "".join(bases)


def _sam_file(tmp_path, contents):
    p = tmp_path / "aln.sam"
    p.write_text("\n".join(contents) + "\n", encoding="utf-8")
    return str(p)


def _reference_monkeypatch(tmp_path, monkeypatch):
    ref_file = tmp_path / "ref.fa"
    ref_file.write_text(f">chr1\n{REF}\n", encoding="utf-8")

    async def fake_download(ref_name: str, dest_dir=None):
        if ref_name != "sars-cov-2":
            raise ValueError(f"Unknown reference genome: {ref_name}")
        return str(ref_file)

    monkeypatch.setattr("app.tools.sequencing._download_reference", fake_download)
    return str(ref_file)


EXPECTED_CONSENSUS = "GGGGGAAAACCACCTTTTGGGGGAAGACCNNNNNNNN"


class TestReferenceKnownVariants:
    def test_known_snv_del_lowcov_consensus(self, tmp_path):
        # Reads A (2x): full depth over 0..39 with deletion + all three SNVs.
        full_del = _read_seq(40, with_del=True, mutations=SNVS)
        a = [_sam_read("A1", "17M1D22M", full_del), _sam_read("A2", "17M1D22M", full_del)]

        # Reads B (2x): cover 0..29, deletion at 17. One carries SNV at 26, one does not.
        b1_seq = _read_seq(30, with_del=True, mutations={11: "A", 26: "G"})
        b2_seq = _read_seq(30, with_del=True, mutations={11: "A"})
        b = [
            _sam_read("B1", "17M1D12M", b1_seq),
            _sam_read("B2", "17M1D12M", b2_seq),
        ]

        sam = _sam_file(tmp_path, a + b)
        pileup = _pileup_reads(sam, REF)
        consensus = _build_consensus(REF, pileup)

        # Index 30..37 are covered by only 2 reads -> N-masked.
        assert consensus.endswith("N" * 8)
        assert consensus == EXPECTED_CONSENSUS
        assert len(consensus) == 37  # 38 ref bases, one deleted, eight masked.

    def test_variant_calls_for_known_snvs_and_del(self, tmp_path):
        full_del = _read_seq(40, with_del=True, mutations=SNVS)
        reads = [_sam_read(f"R{i}", "17M1D22M", full_del) for i in range(4)]
        sam = _sam_file(tmp_path, reads)
        pileup = _pileup_reads(sam, REF)

        by_pos = {v["pos"]: v for v in pileup["variants"]}
        assert set(by_pos) == {12, 18, 27, 38}

        snv12 = by_pos[12]
        assert snv12["type"] == "SNV"
        assert snv12["ref"] == "C" and snv12["alt"] == "A"
        assert snv12["depth"] == 4 and snv12["freq"] == pytest.approx(1.0)

        del18 = by_pos[18]
        assert del18["type"] == "DEL"
        assert del18["ref"] == "T" and del18["alt"] == "*"
        assert del18["depth"] == 4 and del18["freq"] == pytest.approx(1.0)

        snv27 = by_pos[27]
        assert snv27["type"] == "SNV"
        assert snv27["ref"] == "A" and snv27["alt"] == "G"
        assert snv27["depth"] == 4 and snv27["freq"] == pytest.approx(1.0)

        snv38 = by_pos[38]
        assert snv38["type"] == "SNV"
        assert snv38["ref"] == "T" and snv38["alt"] == "C"

    def test_strand_balance_counts(self, tmp_path):
        pairs = []
        for i in range(3):
            pairs.append(_sam_read(f"F{i}", "38M", REF, flag=0))
            pairs.append(_sam_read(f"R{i}", "38M", REF, flag=16))
        sam = _sam_file(tmp_path, pairs)
        pileup = _pileup_reads(sam, REF)
        rec = pileup["positions"][0]
        assert rec["depth"] == 6
        assert rec["strand"]["+"] == 3 and rec["strand"]["-"] == 3
        assert not pileup["variants"]  # no variants at all


class TestInsertionsTallied:
    def test_insertion_increments_ins_count(self, tmp_path):
        seq = REF[:10] + "A" + REF[10:]
        sam = _sam_file(tmp_path, [_sam_read("R0", "10M1I28M", seq)])
        pileup = _pileup_reads(sam, REF)
        total_ins = sum(rec["ins"] for rec in pileup["positions"].values())
        assert total_ins == 1


class TestDegradedContract:
    def test_degraded_when_minimap2_unavailable_and_no_consensus(self, tmp_path, monkeypatch):
        _reference_monkeypatch(tmp_path, monkeypatch)

        async def raise_missing(*a, **k):
            raise FileNotFoundError("minimap2 not installed")

        monkeypatch.setattr("app.tools.sequencing._ensure_minimap2", raise_missing)

        async def go():
            return await SequencingPipeline().run({"fastq_url": "synthetic", "reference": "sars-cov-2"})

        result = asyncio.run(go())

        assert result["status"] == "DEGRADED"
        assert result["fallback_used"] is True
        assert result["validation"]["no_consensus"] is True
        assert result["validation"]["hard_stop_before_consensus"] is True
        assert "consensus_sequence" not in result["results"]
        assert "ai_interpretation" not in result["results"]

    def test_failed_when_no_fastq(self):
        result = asyncio.run(SequencingPipeline().run({"reference": "sars-cov-2"}))
        assert result["status"] == "FAILED"
        assert result["results"]["error"] == "fastq_url is required"

    def test_failed_contract_for_unknown_reference(self):
        # "none" is not a resolvable reference in REFERENCE_URLS -> ValueError,
        # which must still surface as a FAILED ScientificResult, not a bare dict.
        result = asyncio.run(SequencingPipeline().run({"fastq_url": "synthetic", "reference": "none"}))
        assert result["status"] == "FAILED"
        assert result["validation"]["failed_step"] == "input"
        assert "Unknown reference genome" in result["results"]["error"]


class TestValidContractOutput:
    def test_synthetic_run_matches_contract_and_artifacts(self, tmp_path, monkeypatch):
        _reference_monkeypatch(tmp_path, monkeypatch)

        class FakeProc:
            def __init__(self):
                self.returncode = 0
                self.stdout = b""
                self.stderr = b""

            async def communicate(self):
                return self.stdout, self.stderr

        async def fake_exec(*args, **kwargs):
            exe, *rest = args
            out_path = rest[-1]
            full_del = _read_seq(40, with_del=True, mutations=SNVS)
            contents = "\n".join([_sam_read(f"R{i}", "17M1D22M", full_del) for i in range(4)])
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(contents + "\n")
            return FakeProc()

        async def get_mm2(*a, **k):
            return "fake-minimap2"

        monkeypatch.setattr("app.tools.sequencing._ensure_minimap2", get_mm2)
        monkeypatch.setattr(
            "app.tools.sequencing.asyncio.create_subprocess_exec",
            fake_exec,
        )

        async def go():
            return await SequencingPipeline().run(
                {"fastq_url": "synthetic", "reference": "sars-cov-2"}
            )

        result = asyncio.run(go())

        assert result["status"] == "VALID"
        assert result["engine"] == "minimap2"
        assert result["output_sha256"]
        assert len(result["plots"]) == 4
        assert [p["name"] for p in result["plots"]] == [
            "depth_vs_position",
            "base_quality_distribution",
            "allele_fraction_vs_position",
            "variant_type_summary",
        ]
        kinds = {a["kind"] for a in result["artifacts"]}
        assert kinds == {"fastq_qc", "consensus_fasta", "vcf", "depth_table", "provenance", "sam"}
        fasta = next(a["content"] for a in result["artifacts"] if a["kind"] == "consensus_fasta")
        assert fasta.startswith(">sars-cov-2 consensus")
        consensus_seq = fasta.strip().splitlines()[1]
        # Full coverage: 38 ref bases, one deletion -> 37. No uncovered region.
        assert len(consensus_seq) == len(REF) - 1
        assert "N" not in consensus_seq
        assert consensus_seq[11] == "A"  # SNV idx11 applied
        assert consensus_seq[25] == "G"  # SNV idx26 applied (idx25 after deletion shift)

    def test_empty_sam_yields_all_n_consensus(self, tmp_path):
        # No reads -> every position has no support -> all N-masked.
        sam = _sam_file(tmp_path, [])
        pileup = _pileup_reads(sam, REF)
        consensus = _build_consensus(REF, pileup)
        assert consensus == "N" * len(REF)