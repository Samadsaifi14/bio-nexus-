"""Small-reference consensus sequencing with explicit scientific failure states.

This module intentionally has no pseudo-aligner fallback.  If minimap2 cannot
run successfully, alignment-dependent processing stops and the returned
ScientificResult is FAILED.  A failed download is also never replaced with
synthetic reads; synthetic data is used only when explicitly requested.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import platform
import random
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import httpx

from app.science.result import ScientificStatus, build_scientific_result, failed_scientific_result
from app.tools.base import BaseTool

logger = logging.getLogger(__name__)

_IS_WINDOWS = os.name == "nt" or platform.system() == "Windows"
_MINIMAP2_BIN = "minimap2.exe" if _IS_WINDOWS else "minimap2"
BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "bin")
MINIMAP2_PATH = shutil.which("minimap2") or os.path.join(BIN_DIR, _MINIMAP2_BIN)
MINIMAP2_URL = "https://github.com/lh3/minimap2/releases/download/v2.28/minimap2-2.28_x64-linux.tar.bz2"

PIPELINE_TIMEOUT = 600

REFERENCE_URLS = {
    "sars-cov-2": "https://hgdownload.soe.ucsc.edu/goldenPath/wuhCor1/bigZips/wuhCor1.fa.gz",
    "lambda": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NC_001416&rettype=fasta&retmode=text",
}

SMALL_REFERENCE = "sars-cov-2"
MAX_FASTQ_SIZE = 50 * 1024 * 1024
REF_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "references")

DEFAULT_MIN_DEPTH = 10
DEFAULT_MIN_BASE_QUALITY = 20
DEFAULT_MIN_MAPPING_QUALITY = 20
DEFAULT_ALLELE_FREQUENCY = 0.50
DEFAULT_AMBIGUITY_MIN_FREQUENCY = 0.20

_IUPAC_FROM_BASES = {
    frozenset({"A"}): "A", frozenset({"C"}): "C", frozenset({"G"}): "G", frozenset({"T"}): "T",
    frozenset({"A", "G"}): "R", frozenset({"C", "T"}): "Y", frozenset({"G", "C"}): "S",
    frozenset({"A", "T"}): "W", frozenset({"G", "T"}): "K", frozenset({"A", "C"}): "M",
    frozenset({"C", "G", "T"}): "B", frozenset({"A", "G", "T"}): "D",
    frozenset({"A", "C", "T"}): "H", frozenset({"A", "C", "G"}): "V",
    frozenset({"A", "C", "G", "T"}): "N",
}


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reference_sequence(reference_text: str) -> str:
    return "".join(
        line.strip().upper()
        for line in reference_text.splitlines()
        if line.strip() and not line.startswith(">")
    )


def _is_executable(path: str) -> bool:
    if not os.path.exists(path):
        return False
    if _IS_WINDOWS:
        return os.path.isfile(path)
    return os.access(path, os.X_OK)


async def _ensure_minimap2() -> str:
    """Return a real minimap2 executable or fail; never substitute an aligner."""
    if _is_executable(MINIMAP2_PATH):
        return MINIMAP2_PATH
    if _IS_WINDOWS:
        raise FileNotFoundError(
            "minimap2 is required for consensus sequencing and is not installed. "
            "Install minimap2 or run the workflow in the Linux scientific worker."
        )

    dest = MINIMAP2_PATH
    os.makedirs(BIN_DIR, exist_ok=True)
    logger.info("Downloading minimap2 v2.28")
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        response = await client.get(MINIMAP2_URL)
        response.raise_for_status()
        import io
        import tarfile

        with tarfile.open(fileobj=io.BytesIO(response.content)) as archive:
            member = next((m for m in archive.getmembers() if m.name.endswith("/minimap2") or m.name == "minimap2"), None)
            if member is None:
                raise RuntimeError("Downloaded minimap2 archive did not contain the executable")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise RuntimeError("Could not extract minimap2 executable")
            with open(dest, "wb") as handle:
                handle.write(extracted.read())
    os.chmod(dest, 0o700)
    return dest


def _engine_version(binary: str) -> str:
    try:
        proc = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10)
        text = (proc.stdout or proc.stderr or "").strip().splitlines()
        return text[0].strip() if text else "unknown"
    except Exception:
        return "unknown"


def _fallback_alignment(*_args, **_kwargs) -> dict:
    """Removed scientific fallback retained only to fail old callers loudly."""
    raise RuntimeError(
        "The historical Python fallback is not an aligner and is disabled. "
        "Consensus processing must stop when minimap2 is unavailable."
    )


def _generate_synthetic_fastq(ref_seq: str, num_reads: int = 100, read_len: int = 100) -> str:
    """Generate deterministic-quality reference reads for explicit demo use."""
    ref = _reference_sequence(ref_seq)
    if not ref:
        raise ValueError("Reference sequence is empty")
    read_len = max(1, min(read_len, len(ref)))
    rng = random.Random(42)
    lines: list[str] = []
    for i in range(num_reads):
        start = rng.randint(0, max(0, len(ref) - read_len))
        seq = ref[start:start + read_len]
        lines.extend((f"@read{i + 1}", seq, "+", "I" * len(seq)))
    return "\n".join(lines) + "\n"


def _parse_fastq_quality(fastq_path: str) -> dict:
    total_reads = total_bases = gc_count = at_count = 0
    q_scores: list[int] = []
    read_lengths: list[int] = []
    seen_seqs: Counter[str] = Counter()
    quality_histogram: Counter[int] = Counter()

    with open(fastq_path, encoding="utf-8", errors="replace") as handle:
        record: list[str] = []
        for raw_line in handle:
            record.append(raw_line.rstrip("\r\n"))
            if len(record) < 4:
                continue
            header, seq, plus, qual = record
            record = []
            if not header.startswith("@") or not plus.startswith("+"):
                return {"error": "Malformed FASTQ record"}
            if len(seq) != len(qual):
                return {"error": "FASTQ sequence and quality lengths differ"}
            total_reads += 1
            total_bases += len(seq)
            read_lengths.append(len(seq))
            seq_upper = seq.upper()
            gc_count += seq_upper.count("G") + seq_upper.count("C")
            at_count += seq_upper.count("A") + seq_upper.count("T")
            seen_seqs[seq_upper] += 1
            for char in qual:
                q = ord(char) - 33
                q_scores.append(q)
                quality_histogram[q] += 1

    if total_reads == 0:
        return {"error": "Empty FASTQ file", "total_reads": 0}
    if record:
        return {"error": "Truncated FASTQ record"}

    denom = gc_count + at_count
    overrepresented = seen_seqs.most_common(10)
    return {
        "total_reads": total_reads,
        "total_bases": total_bases,
        "avg_read_length": round(sum(read_lengths) / len(read_lengths), 2),
        "min_read_length": min(read_lengths),
        "max_read_length": max(read_lengths),
        "gc_percent": round(gc_count / denom * 100, 2) if denom else 0.0,
        "mean_quality": round(sum(q_scores) / len(q_scores), 2) if q_scores else 0.0,
        "min_quality": min(q_scores) if q_scores else 0,
        "max_quality": max(q_scores) if q_scores else 0,
        "q20_percent": round(sum(q >= 20 for q in q_scores) / len(q_scores) * 100, 2) if q_scores else 0.0,
        "q30_percent": round(sum(q >= 30 for q in q_scores) / len(q_scores) * 100, 2) if q_scores else 0.0,
        "quality_histogram": [{"quality": q, "count": quality_histogram[q]} for q in sorted(quality_histogram)],
        "overrepresented_sequences": [
            {"sequence": seq[:50], "count": count, "percent": round(count / total_reads * 100, 2)}
            for seq, count in overrepresented
        ],
    }


def _empty_base_counter() -> dict[str, int]:
    return {"A": 0, "C": 0, "G": 0, "T": 0, "N": 0}


def _parse_sam_evidence(
    sam_path: str,
    reference_seq: str,
    *,
    min_depth: int,
    min_base_quality: int,
    min_mapping_quality: int,
    min_alt_freq: float,
    ambiguity_min_freq: float,
) -> dict[str, Any]:
    """Parse primary SAM alignments into filtered pileup, variants and consensus."""
    ref = _reference_sequence(reference_seq)
    base_counts: dict[int, dict[str, int]] = defaultdict(_empty_base_counter)
    strand_counts: dict[int, dict[str, int]] = defaultdict(lambda: {"forward": 0, "reverse": 0})
    depth: Counter[int] = Counter()
    insertions: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: {"count": 0, "forward": 0, "reverse": 0})
    deletions: dict[tuple[int, str, str], dict[str, int]] = defaultdict(lambda: {"count": 0, "forward": 0, "reverse": 0})

    stats = {
        "total_alignments": 0,
        "mapped_reads": 0,
        "unmapped_reads": 0,
        "passing_mapq_reads": 0,
        "forward_mapped_reads": 0,
        "reverse_mapped_reads": 0,
    }

    with open(sam_path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line or line.startswith("@"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 11:
                continue
            try:
                flag = int(parts[1])
                pos_1 = int(parts[3])
                mapq = int(parts[4])
            except ValueError:
                continue
            if flag & 0x100 or flag & 0x800:
                continue
            stats["total_alignments"] += 1
            if flag & 0x4:
                stats["unmapped_reads"] += 1
                continue
            stats["mapped_reads"] += 1
            reverse = bool(flag & 0x10)
            stats["reverse_mapped_reads" if reverse else "forward_mapped_reads"] += 1
            if mapq < min_mapping_quality:
                continue
            stats["passing_mapq_reads"] += 1

            cigar, seq, qual = parts[5], parts[9].upper(), parts[10]
            if cigar == "*" or seq == "*":
                continue
            q_scores = None if qual == "*" else [ord(c) - 33 for c in qual]
            ref_i = pos_1 - 1
            query_i = 0
            ops = re.findall(r"(\d+)([MIDNSHP=X])", cigar)
            if not ops:
                continue

            for raw_len, op in ops:
                length = int(raw_len)
                if op in ("M", "=", "X"):
                    for offset in range(length):
                        rpos = ref_i + offset
                        qpos = query_i + offset
                        if rpos < 0 or rpos >= len(ref) or qpos >= len(seq):
                            continue
                        if q_scores is None or qpos >= len(q_scores) or q_scores[qpos] < min_base_quality:
                            continue
                        base = seq[qpos] if seq[qpos] in "ACGT" else "N"
                        depth[rpos] += 1
                        base_counts[rpos][base] += 1
                        strand_counts[rpos]["reverse" if reverse else "forward"] += 1
                    ref_i += length
                    query_i += length
                elif op == "I":
                    inserted = seq[query_i:query_i + length]
                    inserted_q = [] if q_scores is None else q_scores[query_i:query_i + length]
                    if inserted and len(inserted_q) == len(inserted) and all(q >= min_base_quality for q in inserted_q):
                        anchor = max(0, ref_i - 1)
                        if anchor < len(ref):
                            key = (anchor, inserted)
                            insertions[key]["count"] += 1
                            insertions[key]["reverse" if reverse else "forward"] += 1
                    query_i += length
                elif op in ("D", "N"):
                    if op == "D" and length > 0:
                        anchor = max(0, ref_i - 1)
                        deleted = ref[ref_i:ref_i + length]
                        if anchor < len(ref) and deleted:
                            ref_allele = ref[anchor] + deleted
                            alt_allele = ref[anchor]
                            key = (anchor, ref_allele, alt_allele)
                            deletions[key]["count"] += 1
                            deletions[key]["reverse" if reverse else "forward"] += 1
                        for rpos in range(ref_i, min(ref_i + length, len(ref))):
                            depth[rpos] += 1
                            strand_counts[rpos]["reverse" if reverse else "forward"] += 1
                    ref_i += length
                elif op == "S":
                    query_i += length
                elif op in ("H", "P"):
                    continue

    depth_rows: list[dict[str, Any]] = []
    snv_candidates: list[dict[str, Any]] = []
    variants: list[dict[str, Any]] = []
    consensus_chars: list[str] = []

    for rpos, ref_base in enumerate(ref):
        d = int(depth.get(rpos, 0))
        counts = base_counts.get(rpos, _empty_base_counter())
        canonical_total = sum(counts.get(base, 0) for base in "ACGT")
        depth_rows.append({
            "position": rpos + 1,
            "depth": d,
            "forward_depth": strand_counts[rpos]["forward"],
            "reverse_depth": strand_counts[rpos]["reverse"],
            "A": counts.get("A", 0), "C": counts.get("C", 0), "G": counts.get("G", 0), "T": counts.get("T", 0),
        })

        if d < min_depth or canonical_total == 0:
            consensus_chars.append("N")
            continue

        ordered = sorted(((base, counts.get(base, 0)) for base in "ACGT"), key=lambda item: (-item[1], item[0]))
        top_base, top_count = ordered[0]
        top_freq = top_count / canonical_total

        for alt in "ACGT":
            if alt == ref_base:
                continue
            alt_count = counts.get(alt, 0)
            freq = alt_count / canonical_total if canonical_total else 0.0
            if alt_count:
                snv_candidates.append({
                    "pos": rpos + 1, "ref": ref_base, "alt": alt, "depth": canonical_total,
                    "alt_count": alt_count, "freq": round(freq, 6), "type": "SNV",
                    "forward_depth": strand_counts[rpos]["forward"], "reverse_depth": strand_counts[rpos]["reverse"],
                })
            if freq >= min_alt_freq and canonical_total >= min_depth:
                variants.append({
                    "pos": rpos + 1, "ref": ref_base, "alt": alt, "depth": canonical_total,
                    "alt_count": alt_count, "freq": round(freq, 6), "type": "SNV",
                    "forward_depth": strand_counts[rpos]["forward"], "reverse_depth": strand_counts[rpos]["reverse"],
                })

        if top_freq >= min_alt_freq:
            consensus_chars.append(top_base)
        else:
            represented = frozenset(base for base, count in ordered if count / canonical_total >= ambiguity_min_freq)
            consensus_chars.append(_IUPAC_FROM_BASES.get(represented, "N"))

    for (anchor, inserted), support in insertions.items():
        denominator = max(int(depth.get(anchor, 0)), support["count"])
        freq = support["count"] / denominator if denominator else 0.0
        if denominator >= min_depth and freq >= min_alt_freq:
            variants.append({
                "pos": anchor + 1, "ref": ref[anchor], "alt": ref[anchor] + inserted,
                "depth": denominator, "alt_count": support["count"], "freq": round(freq, 6), "type": "INS",
                "forward_depth": support["forward"], "reverse_depth": support["reverse"],
            })

    for (anchor, ref_allele, alt_allele), support in deletions.items():
        denominator = max(int(depth.get(anchor, 0)), support["count"])
        freq = support["count"] / denominator if denominator else 0.0
        if denominator >= min_depth and freq >= min_alt_freq:
            variants.append({
                "pos": anchor + 1, "ref": ref_allele, "alt": alt_allele,
                "depth": denominator, "alt_count": support["count"], "freq": round(freq, 6), "type": "DEL",
                "forward_depth": support["forward"], "reverse_depth": support["reverse"],
            })

    variants.sort(key=lambda item: (item["pos"], item["type"], item["alt"]))

    consensus = "".join(consensus_chars)
    for variant in sorted((v for v in variants if v["type"] in {"INS", "DEL"}), key=lambda item: item["pos"], reverse=True):
        pos = int(variant["pos"])
        if variant["type"] == "INS":
            inserted = variant["alt"][len(variant["ref"]):]
            consensus = consensus[:pos] + inserted + consensus[pos:]
        else:
            deleted_length = len(variant["ref"]) - len(variant["alt"])
            consensus = consensus[:pos] + consensus[pos + deleted_length:]

    callable_positions = sum(row["depth"] >= min_depth for row in depth_rows)
    stats.update({
        "reference_positions": len(ref),
        "callable_positions": callable_positions,
        "callable_fraction": round(callable_positions / len(ref), 6) if ref else 0.0,
    })
    return {
        "alignment": stats,
        "variants": variants,
        "snv_candidates": snv_candidates,
        "depth": depth_rows,
        "consensus": consensus,
    }


def _parse_sam_for_variants(
    sam_path: str,
    reference_seq: str,
    min_depth: int = DEFAULT_MIN_DEPTH,
    min_alt_freq: float = DEFAULT_ALLELE_FREQUENCY,
    min_base_quality: int = DEFAULT_MIN_BASE_QUALITY,
    min_mapping_quality: int = DEFAULT_MIN_MAPPING_QUALITY,
) -> list[dict]:
    parsed = _parse_sam_evidence(
        sam_path,
        reference_seq,
        min_depth=min_depth,
        min_base_quality=min_base_quality,
        min_mapping_quality=min_mapping_quality,
        min_alt_freq=min_alt_freq,
        ambiguity_min_freq=DEFAULT_AMBIGUITY_MIN_FREQUENCY,
    )
    return parsed["variants"]


def _build_consensus(reference_seq: str, variants: list[dict]) -> str:
    ref = list(_reference_sequence(reference_seq))
    for variant in sorted(variants, key=lambda item: item.get("pos", 0), reverse=True):
        pos = int(variant.get("pos", 0))
        if pos < 1 or pos > len(ref):
            continue
        vtype = variant.get("type", "SNV")
        if vtype == "SNV" and len(variant.get("alt", "")) == 1:
            ref[pos - 1] = variant["alt"]
        elif vtype == "INS":
            inserted = variant.get("alt", "")[len(variant.get("ref", "")):]
            ref[pos:pos] = list(inserted)
        elif vtype == "DEL":
            delete_n = max(0, len(variant.get("ref", "")) - len(variant.get("alt", "")))
            del ref[pos:pos + delete_n]
    return "".join(ref)


def _downsample_depth(rows: list[dict[str, Any]], max_points: int = 2000) -> list[dict[str, Any]]:
    if len(rows) <= max_points:
        return [{"position": row["position"], "depth": row["depth"]} for row in rows]
    stride = max(1, len(rows) // max_points)
    return [{"position": row["position"], "depth": row["depth"]} for row in rows[::stride]][:max_points]


def _variant_type_counts(variants: list[dict]) -> list[dict[str, Any]]:
    counts = Counter(v.get("type", "OTHER") for v in variants)
    return [{"type": key, "count": counts.get(key, 0)} for key in ("SNV", "INS", "DEL")]


def _vcf_text(reference: str, variants: list[dict], params: dict[str, Any]) -> str:
    lines = [
        "##fileformat=VCFv4.2",
        f"##source=BioNexus-consensus-sequencing",
        f"##reference={reference}",
        f"##BioNexusMinDepth={params['min_depth']}",
        f"##BioNexusMinBaseQuality={params['min_base_quality']}",
        f"##BioNexusMinMappingQuality={params['min_mapping_quality']}",
        f"##BioNexusAlleleFrequency={params['allele_frequency']}",
        "##INFO=<ID=DP,Number=1,Type=Integer,Description=Filtered depth>",
        "##INFO=<ID=AF,Number=1,Type=Float,Description=Allele fraction>",
        "##INFO=<ID=TYPE,Number=1,Type=String,Description=Variant type>",
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
    ]
    for variant in variants:
        lines.append(
            f"{reference}\t{variant['pos']}\t.\t{variant['ref']}\t{variant['alt']}\t.\tPASS\t"
            f"DP={variant['depth']};AF={variant['freq']};TYPE={variant['type']}"
        )
    return "\n".join(lines) + "\n"


def _depth_tsv(rows: list[dict[str, Any]]) -> str:
    header = "position\tdepth\tforward_depth\treverse_depth\tA\tC\tG\tT"
    body = [
        f"{r['position']}\t{r['depth']}\t{r['forward_depth']}\t{r['reverse_depth']}\t{r['A']}\t{r['C']}\t{r['G']}\t{r['T']}"
        for r in rows
    ]
    return header + "\n" + "\n".join(body) + "\n"


async def _download_fastq(url: str, dest: str) -> str:
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_length = int(response.headers.get("content-length", 0) or 0)
            if content_length > MAX_FASTQ_SIZE:
                raise ValueError(f"FASTQ too large: {content_length} bytes (max {MAX_FASTQ_SIZE})")
            size = 0
            with open(dest, "wb") as handle:
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_FASTQ_SIZE:
                        raise ValueError(f"FASTQ exceeds maximum size of {MAX_FASTQ_SIZE} bytes")
                    handle.write(chunk)
    return dest


async def _download_reference(ref_name: str, dest_dir: str | None = None) -> str:
    url = REFERENCE_URLS.get(ref_name)
    if not url:
        raise ValueError(f"Unknown reference genome: {ref_name}")
    cache_dir = dest_dir or REF_CACHE_DIR
    os.makedirs(cache_dir, exist_ok=True)
    fa_path = os.path.join(cache_dir, f"{ref_name}.fa")
    if os.path.exists(fa_path) and os.path.getsize(fa_path) > 0:
        return fa_path
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.content
        if url.endswith(".gz"):
            import gzip
            data = gzip.decompress(data)
        with open(fa_path, "wb") as handle:
            handle.write(data)
    return fa_path


def _persist_artifacts(
    job_id: str | None,
    *,
    fastq_qc: dict,
    sam_path: str,
    ref_path: str,
    reference: str,
    vcf_text: str,
    depth_text: str,
    consensus_fasta: str,
    provenance: dict,
) -> list[dict[str, Any]]:
    payloads: list[tuple[str, str, str]] = [
        ("fastq_qc.json", json.dumps(fastq_qc, sort_keys=True, indent=2), "application/json"),
        ("alignment.sam", Path(sam_path).read_text(encoding="utf-8", errors="replace"), "text/plain"),
        ("variants.vcf", vcf_text, "text/plain"),
        ("depth.tsv", depth_text, "text/tab-separated-values"),
        ("consensus.fasta", consensus_fasta, "text/x-fasta"),
        ("provenance.json", json.dumps(provenance, sort_keys=True, indent=2), "application/json"),
    ]
    artifacts: list[dict[str, Any]] = []
    if not job_id:
        for name, content, media_type in payloads:
            artifacts.append({"name": name, "media_type": media_type, "available": False, "reason": "No durable job id supplied", "sha256": hashlib.sha256(content.encode()).hexdigest()})
        return artifacts

    from app.services.artifact_storage import upload_artifact, upload_bytes_artifact

    for name, content, media_type in payloads:
        digest = hashlib.sha256(content.encode()).hexdigest()
        try:
            url = upload_artifact(job_id, name, content, media_type)
            artifacts.append({"name": name, "media_type": media_type, "url": url, "sha256": digest, "available": True})
        except Exception as exc:
            logger.warning("Could not persist sequencing artifact %s: %s", name, type(exc).__name__)
            artifacts.append({"name": name, "media_type": media_type, "sha256": digest, "available": False, "reason": "Artifact storage unavailable"})

    samtools = shutil.which("samtools")
    if samtools:
        bam_path = str(Path(sam_path).with_suffix(".bam"))
        bai_path = bam_path + ".bai"
        try:
            subprocess.run([samtools, "sort", "-o", bam_path, sam_path], check=True, capture_output=True, timeout=120)
            subprocess.run([samtools, "index", bam_path], check=True, capture_output=True, timeout=120)
            for path, media_type in ((bam_path, "application/octet-stream"), (bai_path, "application/octet-stream")):
                data = Path(path).read_bytes()
                url = upload_bytes_artifact(job_id, Path(path).name, data, media_type)
                artifacts.append({"name": Path(path).name, "media_type": media_type, "url": url, "sha256": hashlib.sha256(data).hexdigest(), "available": True})
        except Exception as exc:
            logger.warning("SAM->BAM/index export unavailable: %s", type(exc).__name__)

    try:
        ref_bytes = Path(ref_path).read_bytes()
        url = upload_bytes_artifact(job_id, f"{reference}.fa", ref_bytes, "text/x-fasta")
        artifacts.append({"name": f"{reference}.fa", "media_type": "text/x-fasta", "url": url, "sha256": hashlib.sha256(ref_bytes).hexdigest(), "available": True, "role": "reference"})
    except Exception:
        pass
    return artifacts


class SequencingPipeline(BaseTool):
    name = "sequencing"

    async def run(self, input: dict) -> dict:
        fastq_url = str(input.get("fastq_url", "")).strip()
        reference = str(input.get("reference", SMALL_REFERENCE)).strip().lower()
        job_id = str(input.get("job_id") or "").strip() or None
        params = {
            "min_depth": max(1, int(input.get("min_depth", DEFAULT_MIN_DEPTH))),
            "min_base_quality": max(0, int(input.get("min_base_quality", DEFAULT_MIN_BASE_QUALITY))),
            "min_mapping_quality": max(0, int(input.get("min_mapping_quality", DEFAULT_MIN_MAPPING_QUALITY))),
            "allele_frequency": float(input.get("allele_frequency", DEFAULT_ALLELE_FREQUENCY)),
            "ambiguity_min_frequency": float(input.get("ambiguity_min_frequency", DEFAULT_AMBIGUITY_MIN_FREQUENCY)),
            "minimap2_preset": "sr",
        }
        if not (0.0 < params["allele_frequency"] <= 1.0):
            raise ValueError("allele_frequency must be in (0, 1]")
        if not (0.0 < params["ambiguity_min_frequency"] <= params["allele_frequency"]):
            raise ValueError("ambiguity_min_frequency must be >0 and <= allele_frequency")

        input_manifest = {"fastq_url": fastq_url, "reference": reference, "parameters": params}
        if not fastq_url:
            return failed_scientific_result(
                method="reference-guided consensus sequencing", engine="minimap2", engine_version="unavailable",
                input_payload=input_manifest, reason="fastq_url is required", parameters=params,
            )

        tmpdir = tempfile.mkdtemp(prefix="seqpipe_")
        try:
            try:
                ref_path = await _download_reference(reference)
            except Exception as exc:
                return failed_scientific_result(
                    method="reference-guided consensus sequencing", engine="minimap2", engine_version="unavailable",
                    input_payload=input_manifest, reason=f"Reference retrieval failed: {type(exc).__name__}", parameters=params,
                    database="reference genome", database_version=reference,
                )
            ref_content = Path(ref_path).read_text(encoding="utf-8", errors="replace")
            ref_seq = _reference_sequence(ref_content)
            if not ref_seq:
                return failed_scientific_result(
                    method="reference-guided consensus sequencing", engine="minimap2", engine_version="unavailable",
                    input_payload=input_manifest, reason="Reference FASTA contains no sequence", parameters=params,
                )

            fastq_path = os.path.join(tmpdir, "input.fastq")
            synthetic = fastq_url.lower() in {"synthetic", "demo", "test"}
            if synthetic:
                Path(fastq_path).write_text(_generate_synthetic_fastq(ref_content, num_reads=500, read_len=min(100, len(ref_seq))), encoding="utf-8")
                fastq_source = "synthetic-explicit-demo"
            else:
                try:
                    await asyncio.wait_for(_download_fastq(fastq_url, fastq_path), timeout=120)
                except Exception as exc:
                    return failed_scientific_result(
                        method="reference-guided consensus sequencing", engine="minimap2", engine_version="unavailable",
                        input_payload=input_manifest, reason=f"FASTQ retrieval failed: {type(exc).__name__}", parameters=params,
                        validation={"synthetic_substitution_used": False},
                    )
                fastq_source = "remote-fastq"

            qc = _parse_fastq_quality(fastq_path)
            if qc.get("error"):
                return failed_scientific_result(
                    method="reference-guided consensus sequencing", engine="minimap2", engine_version="unavailable",
                    input_payload={**input_manifest, "fastq_sha256": _sha256_file(fastq_path)}, reason=str(qc["error"]), parameters=params,
                )

            try:
                mm2_path = await asyncio.wait_for(_ensure_minimap2(), timeout=120)
            except Exception as exc:
                return failed_scientific_result(
                    method="reference-guided consensus sequencing", engine="minimap2", engine_version="unavailable",
                    input_payload={**input_manifest, "fastq_sha256": _sha256_file(fastq_path), "reference_sha256": _sha256_file(ref_path)},
                    reason=str(exc), parameters=params,
                    validation={"alignment_completed": False, "variant_calling_executed": False, "consensus_constructed": False},
                )

            version = _engine_version(mm2_path)
            sam_path = os.path.join(tmpdir, "alignment.sam")
            process = await asyncio.create_subprocess_exec(
                mm2_path, "-ax", "sr", ref_path, fastq_path, "-o", sam_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                return failed_scientific_result(
                    method="reference-guided consensus sequencing", engine="minimap2", engine_version=version,
                    input_payload=input_manifest, reason="Alignment timed out after 5 minutes", parameters=params,
                    validation={"alignment_completed": False, "variant_calling_executed": False, "consensus_constructed": False},
                )
            if process.returncode != 0 or not os.path.exists(sam_path) or os.path.getsize(sam_path) == 0:
                message = stderr.decode("utf-8", errors="replace")[:500] if stderr else "no stderr"
                return failed_scientific_result(
                    method="reference-guided consensus sequencing", engine="minimap2", engine_version=version,
                    input_payload=input_manifest, reason=f"minimap2 failed (exit {process.returncode}): {message}", parameters=params,
                    validation={"alignment_completed": False, "variant_calling_executed": False, "consensus_constructed": False},
                )

            parsed = _parse_sam_evidence(
                sam_path, ref_content,
                min_depth=params["min_depth"], min_base_quality=params["min_base_quality"],
                min_mapping_quality=params["min_mapping_quality"], min_alt_freq=params["allele_frequency"],
                ambiguity_min_freq=params["ambiguity_min_frequency"],
            )
            alignment = parsed["alignment"]
            variants = parsed["variants"]
            consensus = parsed["consensus"]
            depth_rows = parsed["depth"]

            status = ScientificStatus.VALID
            warnings: list[str] = []
            if alignment["mapped_reads"] == 0 or alignment["callable_positions"] == 0:
                status = ScientificStatus.DEGRADED
                warnings.append("No reference positions met the declared consensus depth/quality gates")

            consensus_fasta = f">{reference} consensus;min_depth={params['min_depth']};min_bq={params['min_base_quality']};min_mapq={params['min_mapping_quality']};af={params['allele_frequency']}\n{consensus}\n"
            vcf = _vcf_text(reference, variants, params)
            depth_tsv = _depth_tsv(depth_rows)
            type_counts = _variant_type_counts(variants)
            provenance = {
                "method": "reference-guided consensus sequencing",
                "engine": "minimap2",
                "engine_version": version,
                "reference": reference,
                "reference_sha256": _sha256_file(ref_path),
                "fastq_sha256": _sha256_file(fastq_path),
                "fastq_source": fastq_source,
                "parameters": params,
                "synthetic_demo": synthetic,
            }
            artifacts = _persist_artifacts(
                job_id,
                fastq_qc=qc, sam_path=sam_path, ref_path=ref_path, reference=reference,
                vcf_text=vcf, depth_text=depth_tsv, consensus_fasta=consensus_fasta, provenance=provenance,
            )

            plots = [
                {
                    "id": "depth_vs_position", "title": "Depth vs position", "x": "position", "y": "depth",
                    "data": _downsample_depth(depth_rows), "calculated_points": len(depth_rows),
                    "displayed_points": min(len(depth_rows), 2000), "source_artifact": "depth.tsv",
                },
                {
                    "id": "base_quality_distribution", "title": "Base-quality distribution", "x": "quality", "y": "count",
                    "data": qc.get("quality_histogram", []), "source": "FASTQ Phred+33 qualities",
                },
                {
                    "id": "allele_fraction_vs_position", "title": "Allele fraction vs position", "x": "position", "y": "allele_fraction",
                    "data": [{"position": v["pos"], "allele_fraction": v["freq"], "type": v["type"], "ref": v["ref"], "alt": v["alt"]} for v in variants],
                    "source_artifact": "variants.vcf",
                },
                {
                    "id": "variant_type_summary", "title": "Variant type/count summary", "x": "type", "y": "count",
                    "data": type_counts, "source_artifact": "variants.vcf",
                },
            ]

            scientific_input = {
                "fastq_sha256": provenance["fastq_sha256"],
                "reference_sha256": provenance["reference_sha256"],
                "parameters": params,
            }
            result_payload = {
                "reference": reference,
                "reference_length": len(ref_seq),
                "fastq_source": fastq_source,
                "synthetic_demo": synthetic,
                "qc": qc,
                "alignment": alignment,
                "variants": variants,
                "consensus_sequence": consensus_fasta,
                "consensus_callable_fraction": alignment["callable_fraction"],
                "variant_summary": {
                    "total_variants": len(variants),
                    "snv_count": sum(v["type"] == "SNV" for v in variants),
                    "insertion_count": sum(v["type"] == "INS" for v in variants),
                    "deletion_count": sum(v["type"] == "DEL" for v in variants),
                },
                "warnings": warnings,
                "steps_completed": ["qc", "align", "variants", "consensus", "report"],
            }
            validation = {
                "alignment_completed": True,
                "variant_calling_executed": True,
                "consensus_constructed": True,
                "quality_filters_applied": True,
                "low_coverage_mask": "N",
                "indels_handled": True,
                "strand_information_recorded": True,
                "synthetic_demo_only": synthetic,
                "biological_accuracy_established": False,
                "no_variant_wording": "No variants passed the declared thresholds" if not variants else None,
            }
            return build_scientific_result(
                status=status,
                method="reference-guided consensus sequencing",
                engine="minimap2",
                engine_version=version,
                database="reference genome",
                database_version=reference,
                input_payload=scientific_input,
                parameters=params,
                results=result_payload,
                plots=plots,
                artifacts=artifacts,
                evidence_class="Deterministic computation",
                validation=validation,
                citations=[{"label": "minimap2", "url": "https://github.com/lh3/minimap2"}],
            )

        except ValueError as exc:
            return failed_scientific_result(
                method="reference-guided consensus sequencing", engine="minimap2", engine_version="unknown",
                input_payload=input_manifest, reason=str(exc), parameters=params,
            )
        except httpx.HTTPStatusError as exc:
            return failed_scientific_result(
                method="reference-guided consensus sequencing", engine="minimap2", engine_version="unknown",
                input_payload=input_manifest, reason=f"Download failed (HTTP {exc.response.status_code})", parameters=params,
            )
        except Exception as exc:
            logger.exception("Consensus sequencing failed")
            return failed_scientific_result(
                method="reference-guided consensus sequencing", engine="minimap2", engine_version="unknown",
                input_payload=input_manifest, reason=f"Pipeline failed: {type(exc).__name__}: {exc}", parameters=params,
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
