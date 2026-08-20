"""
NGS (Next-Generation Sequencing) Pipeline — 6-step analysis:

1. Quality Control  (FastQC or Python fallback)
2. Trimming/Filter  (fastp or Python fallback)
3. Alignment        (minimap2 + samtools or Python fallback)
4. Variant Calling  (bcftools or Python fallback)
5. Annotation       (SnpEff or cross-reference lookup)
6. Visualization    (upload BAM/VCF/FASTA for igv.js browser)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import random
import re
import shutil
import subprocess
import tempfile
from typing import Any

import httpx

from app.tools.base import BaseTool

logger = logging.getLogger(__name__)

_IS_WINDOWS = os.name == "nt" or platform.system() == "Windows"

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "bin")
PIPELINE_TIMEOUT = 600

REFERENCE_URLS = {
    "sars-cov-2": "https://hgdownload.soe.ucsc.edu/goldenPath/wuhCor1/bigZips/wuhCor1.fa.gz",
    "lambda": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NC_001416&rettype=fasta&retmode=text",
    "ecoli-k12": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=U00096.3&rettype=fasta&retmode=text",
}

REFERENCE_SIZES = {
    "sars-cov-2": 29903,
    "lambda": 48502,
    "ecoli-k12": 4641652,
}

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "references")


# ---------------------------------------------------------------------------
# Tool detection
# ---------------------------------------------------------------------------

def _find_tool(name: str) -> str | None:
    exe = f"{name}.exe" if _IS_WINDOWS else name
    found = shutil.which(name)
    if found:
        return found
    bundled = os.path.join(BIN_DIR, exe)
    if os.path.isfile(bundled):
        return bundled
    return None


def _tool_available(name: str) -> bool:
    path = _find_tool(name)
    if not path:
        return False
    if _IS_WINDOWS:
        return os.path.isfile(path)
    return os.access(path, os.X_OK)


# ---------------------------------------------------------------------------
# Step 1: Quality Control
# ---------------------------------------------------------------------------

def _run_fastqc(fastq_path: str, out_dir: str) -> dict:
    if _tool_available("fastqc"):
        try:
            subprocess.run(
                ["fastqc", fastq_path, "-o", out_dir, "-q", "--json"],
                capture_output=True, text=True, timeout=120,
            )
            json_file = os.path.join(out_dir, os.path.basename(fastq_path).replace(".fastq", "_fastqc.json"))
            if os.path.exists(json_file):
                with open(json_file) as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("FastQC failed, using Python fallback: %s", e)
    return _python_qc(fastq_path)


def _python_qc(fastq_path: str) -> dict:
    total_reads = 0
    total_bases = 0
    gc_count = 0
    at_count = 0
    q_scores: list[int] = []
    read_lengths: list[int] = []
    seen_seqs: dict[str, int] = {}
    base_quality_by_pos: dict[int, list[int]] = {}
    gc_by_window: list[float] = []
    line_no = 0
    window_seqs: list[str] = []
    WINDOW_SIZE = 50

    with open(fastq_path) as f:
        for line in f:
            line_no += 1
            if line_no % 4 == 2:
                seq = line.strip()
                l = len(seq)
                read_lengths.append(l)
                total_bases += l
                total_reads += 1
                gc_count += seq.count("G") + seq.count("C") + seq.count("g") + seq.count("c")
                at_count += seq.count("A") + seq.count("T") + seq.count("a") + seq.count("t")
                seen_seqs[seq] = seen_seqs.get(seq, 0) + 1
                window_seqs.append(seq)
                if len(window_seqs) >= WINDOW_SIZE:
                    gc_in_window = sum(
                        s.count("G") + s.count("C") + s.count("g") + s.count("c")
                        for s in window_seqs
                    )
                    bases_in_window = sum(len(s) for s in window_seqs)
                    gc_by_window.append(round(gc_in_window / max(bases_in_window, 1) * 100, 2))
                    window_seqs = []
            elif line_no % 4 == 0:
                qual_line = line.strip()
                for i, ch in enumerate(qual_line):
                    q = ord(ch) - 33
                    q_scores.append(q)
                    if i not in base_quality_by_pos:
                        base_quality_by_pos[i] = []
                    base_quality_by_pos[i].append(q)

    if window_seqs:
        gc_in_window = sum(s.count("G") + s.count("C") + s.count("g") + s.count("c") for s in window_seqs)
        bases_in_window = sum(len(s) for s in window_seqs)
        gc_by_window.append(round(gc_in_window / max(bases_in_window, 1) * 100, 2))

    if total_reads == 0:
        return {"error": "Empty FASTQ file", "total_reads": 0}

    mean_q = sum(q_scores) / len(q_scores) if q_scores else 0
    q20 = sum(1 for q in q_scores if q >= 20) / len(q_scores) * 100 if q_scores else 0
    q30 = sum(1 for q in q_scores if q >= 30) / len(q_scores) * 100 if q_scores else 0
    gc_pct = gc_count / (gc_count + at_count) * 100 if (gc_count + at_count) > 0 else 0

    # Per-position quality for the chart (sample every N positions)
    max_pos = max(base_quality_by_pos.keys()) if base_quality_by_pos else 0
    sample_step = max(1, max_pos // 100)
    quality_by_position = []
    for pos in range(0, max_pos + 1, sample_step):
        scores = base_quality_by_pos.get(pos, [])
        if scores:
            quality_by_position.append({
                "position": pos,
                "mean": round(sum(scores) / len(scores), 1),
                "q10": round(sorted(scores)[len(scores) // 4], 1) if len(scores) >= 4 else 0,
                "q90": round(sorted(scores)[len(scores) * 3 // 4], 1) if len(scores) >= 4 else 0,
            })

    overrepresented = sorted(seen_seqs.items(), key=lambda x: -x[1])[:10]

    # Read length distribution
    length_dist: dict[int, int] = {}
    for rl in read_lengths:
        bucket = (rl // 10) * 10
        length_dist[bucket] = length_dist.get(bucket, 0) + 1

    return {
        "tool": "python-qc",
        "total_reads": total_reads,
        "total_bases": total_bases,
        "avg_read_length": round(sum(read_lengths) / len(read_lengths), 1),
        "min_read_length": min(read_lengths),
        "max_read_length": max(read_lengths),
        "gc_percent": round(gc_pct, 2),
        "mean_quality": round(mean_q, 2),
        "min_quality": min(q_scores),
        "max_quality": max(q_scores),
        "q20_percent": round(q20, 2),
        "q30_percent": round(q30, 2),
        "quality_by_position": quality_by_position,
        "gc_by_window": gc_by_window,
        "read_length_distribution": [{"length": k, "count": v} for k, v in sorted(length_dist.items())],
        "overrepresented_sequences": [
            {"sequence": s[:50], "count": c, "percent": round(c / total_reads * 100, 2)}
            for s, c in overrepresented
        ],
    }


# ---------------------------------------------------------------------------
# Step 2: Trimming/Filtering
# ---------------------------------------------------------------------------

def _run_fastp(fastq_in: str, fastq_out: str, report_dir: str) -> dict:
    if _tool_available("fastp"):
        report_json = os.path.join(report_dir, "fastp_report.json")
        try:
            subprocess.run(
                ["fastp", "-i", fastq_in, "-o", fastq_out,
                 "--json", report_json, "--thread", "1",
                 "--qualified_quality_phred", "20",
                 "--length_required", "50"],
                capture_output=True, text=True, timeout=120,
            )
            if os.path.exists(report_json):
                with open(report_json) as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("fastp failed, using Python fallback: %s", e)
    return _python_trim(fastq_in, fastq_out)


def _python_trim(fastq_in: str, fastq_out: str) -> dict:
    kept = 0
    discarded = 0
    line_no = 0
    buf: list[str] = []
    before_lengths: list[int] = []
    after_lengths: list[int] = []

    with open(fastq_in) as fin, open(fastq_out, "w") as out:
        for line in fin:
            line_no += 1
            buf.append(line)
            if line_no % 4 == 0:
                seq = buf[1].strip()
                qual = buf[3].strip()
                before_lengths.append(len(seq))
                if len(seq) < 50:
                    discarded += 1
                    buf.clear()
                    continue
                q_scores = [ord(ch) - 33 for ch in qual]
                mean_q = sum(q_scores) / len(q_scores) if q_scores else 0
                if mean_q >= 20:
                    out.writelines(buf)
                    kept += 1
                    after_lengths.append(len(seq))
                else:
                    discarded += 1
                buf.clear()

    avg_before = round(sum(before_lengths) / max(len(before_lengths), 1), 1)
    avg_after = round(sum(after_lengths) / max(len(after_lengths), 1), 1)

    # Quality distribution before/after
    q_before = [ord(ch) - 33 for line in open(fastq_in) for ch in line.strip() if line.strip()]

    return {
        "tool": "python-trim",
        "before_filtering": {"total_reads": kept + discarded, "total_bases": sum(before_lengths), "avg_length": avg_before},
        "after_filtering": {"total_reads": kept, "total_bases": sum(after_lengths), "avg_length": avg_after},
        "reads_discarded": discarded,
        "filtering_result": {"low_quality_reads": discarded},
    }


# ---------------------------------------------------------------------------
# Step 3: Alignment
# ---------------------------------------------------------------------------

def _run_alignment(fastq_path: str, ref_path: str, tmpdir: str) -> dict:
    sam_path = os.path.join(tmpdir, "aligned.sam")
    bam_path = os.path.join(tmpdir, "sorted.bam")
    bai_path = os.path.join(tmpdir, "sorted.bam.bai")

    mm2 = _find_tool("minimap2")
    samtools = _find_tool("samtools")

    if mm2 and samtools and not _IS_WINDOWS:
        try:
            with open(sam_path, "w") as sam_out:
                proc = subprocess.run(
                    [mm2, "-ax", "sr", ref_path, fastq_path],
                    stdout=sam_out, stderr=subprocess.PIPE, timeout=300,
                )
            if proc.returncode != 0:
                logger.warning("minimap2 returned %d: %s", proc.returncode, proc.stderr[:200])

            subprocess.run(
                ["samtools", "sort", "-o", bam_path, sam_path],
                capture_output=True, timeout=120,
            )
            subprocess.run(
                ["samtools", "index", bam_path],
                capture_output=True, timeout=60,
            )

            stats = _parse_alignment_stats(sam_path)
            stats["tool"] = "minimap2+samtools"
            stats["bam_path"] = bam_path
            stats["bai_path"] = bai_path
            stats["sam_path"] = sam_path
            return stats
        except Exception as e:
            logger.warning("Native alignment failed, using Python fallback: %s", e)

    return _python_alignment(fastq_path, ref_path, sam_path)


def _python_alignment(fastq_path: str, ref_path: str, sam_path: str) -> dict:
    ref_name = "unknown"
    ref_seq_lines = []
    with open(ref_path) as rf:
        for line in rf:
            if line.startswith(">"):
                ref_name = line.strip().split()[0][1:].split()[0]
            else:
                ref_seq_lines.append(line.strip())
    ref_seq = "".join(ref_seq_lines)
    ref_len = len(ref_seq) if ref_seq else 30000

    # Build minimap2-style alignment: match reads against reference
    total = 0
    mapped = 0
    unmapped = 0
    reads: list[tuple[str, str, str, int, str, str]] = []

    with open(fastq_path) as fin:
        line_no = 0
        qname = ""
        seq = ""
        qual = ""
        for line in fin:
            line_no += 1
            if line_no % 4 == 1:
                qname = line.strip().lstrip("@")
            elif line_no % 4 == 2:
                seq = line.strip()
            elif line_no % 4 == 0:
                qual = line.strip()
                total += 1
                reads.append((qname, seq, qual))

    # Simple seed-and-extend alignment: find best match in reference
    import random as _rnd
    for qname, seq, qual in reads:
        if len(seq) < 20:
            unmapped += 1
            continue

        # Take a 20bp seed from the read and scan the reference
        seed = seq[:20].upper()
        best_pos = -1
        best_score = 0

        # Scan reference with a sliding window (sample positions for speed)
        step = max(1, ref_len // 500)
        for pos in range(0, ref_len - len(seq), step):
            ref_window = ref_seq[pos:pos + len(seq)]
            matches = sum(1 for a, b in zip(seed, ref_window) if a == b)
            if matches > best_score:
                best_score = matches
                best_pos = pos

        # Refine best position
        if best_pos >= 0 and best_score >= 10:
            # Calculate CIGAR - use M for both match and mismatch (SAM spec)
            ref_segment = ref_seq[best_pos:best_pos + len(seq)]
            cigar_ops = []
            match_count = 0
            for i in range(min(len(seq), len(ref_segment))):
                if seq[i].upper() == ref_segment[i].upper():
                    match_count += 1
                else:
                    if match_count > 0:
                        cigar_ops.append(f"{match_count}M")
                        match_count = 0
                    # Use M not X - igv.js requires standard CIGAR ops
                    cigar_ops.append("1M")
            if match_count > 0:
                cigar_ops.append(f"{match_count}M")

            cigar = "".join(cigar_ops) if cigar_ops else f"{len(seq)}M"
            # Collapse consecutive M operations: 3M1M1M -> 5M, 63M37M -> 100M
            prev = None
            while prev != cigar:
                prev = cigar
                cigar = re.sub(r'(\d+)M(\d+)M', lambda m: f"{int(m.group(1)) + int(m.group(2))}M", cigar)

            # MAPQ: proportional to match quality
            mapq = min(60, best_score * 3)

            # Ensure quality string matches sequence length
            if len(qual) < len(seq):
                qual = qual + "I" * (len(seq) - len(qual))
            qual = qual[:len(seq)]

            # SAM flag: 0 = single-end, mapped
            flag = 0
            reads[reads.index((qname, seq, qual))] = (qname, seq, qual, best_pos + 1, cigar, flag, mapq)
            mapped += 1
        else:
            unmapped += 1

    # Write SAM
    with open(sam_path, "w") as out:
        out.write(f"@HD\tVN:1.6\tSO:coordinate\n")
        out.write(f"@SQ\tSN:{ref_name}\tLN:{ref_len}\n")
        for read in reads:
            if len(read) == 3:
                # Unmapped
                qname, seq, qual = read
                if len(qual) < len(seq):
                    qual = qual + "I" * (len(seq) - len(qual))
                qual = qual[:len(seq)]
                out.write(f"{qname}\t4\t*\t0\t0\t*\t*\t0\t0\t{seq}\t{qual}\n")
            else:
                qname, seq, qual, pos, cigar, flag, mapq = read
                out.write(f"{qname}\t{flag}\t{ref_name}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{seq}\t{qual}\n")

    return {
        "tool": "python-alignment",
        "mapped_reads": mapped,
        "unmapped_reads": unmapped,
        "total_alignments": total,
        "sam_path": sam_path,
    }


def _parse_alignment_stats(sam_path: str) -> dict:
    mapped = 0
    unmapped = 0
    total = 0
    with open(sam_path) as f:
        for line in f:
            if line.startswith("@"):
                continue
            total += 1
            parts = line.strip().split("\t", maxsplit=2)
            if len(parts) >= 2:
                flag = int(parts[1])
                if flag & 4:
                    unmapped += 1
                else:
                    mapped += 1
    return {"mapped_reads": mapped, "unmapped_reads": unmapped, "total_alignments": total}


# ---------------------------------------------------------------------------
# Step 4: Variant Calling
# ---------------------------------------------------------------------------

def _run_variant_calling(sam_path: str, ref_path: str, tmpdir: str) -> dict:
    vcf_path = os.path.join(tmpdir, "variants.vcf")
    bcftools = _find_tool("bcftools")
    samtools = _find_tool("samtools")

    if bcftools and samtools and not _IS_WINDOWS:
        try:
            bam_path = os.path.join(tmpdir, "sorted.bam")
            if not os.path.exists(bam_path):
                return _python_variant_calling(sam_path, ref_path, vcf_path)

            proc = subprocess.run(
                ["bcftools", "mpileup", "-f", ref_path, bam_path, "-O", "u"],
                capture_output=True, timeout=120,
            )
            if proc.returncode != 0:
                return _python_variant_calling(sam_path, ref_path, vcf_path)

            call_proc = subprocess.run(
                ["bcftools", "call", "-mv", "-O", "v"],
                input=proc.stdout, capture_output=True, timeout=120,
            )
            with open(vcf_path, "w") as f:
                f.write(call_proc.stdout.decode("utf-8", errors="replace"))

            variants = _parse_vcf(vcf_path)
            return {
                "tool": "bcftools",
                "vcf_path": vcf_path,
                "variants": variants,
                "total_variants": len(variants),
            }
        except Exception as e:
            logger.warning("bcftools failed, using Python fallback: %s", e)

    return _python_variant_calling(sam_path, ref_path, vcf_path)


def _python_variant_calling(sam_path: str, ref_path: str, vcf_path: str) -> dict:
    ref_lines = open(ref_path).readlines()
    ref_name = "unknown"
    ref_seq_lines = []
    for line in ref_lines:
        if line.startswith(">"):
            ref_name = line.strip().split()[0][1:].split()[0]
        else:
            ref_seq_lines.append(line.strip())
    ref = "".join(ref_seq_lines)

    pileup: dict[int, dict[str, int]] = {}
    depth_by_pos: dict[int, int] = {}

    with open(sam_path) as f:
        for line in f:
            if line.startswith("@"):
                continue
            parts = line.strip().split("\t")
            if len(parts) < 6:
                continue
            flag = int(parts[1])
            if flag & 4:
                continue
            pos = int(parts[3])
            cigar = parts[5]
            seq = parts[9]

            genome_pos = pos - 1
            ops = re.findall(r"(\d+)([MIDNSHPX=])", cigar)
            offset = 0
            for length, op in ops:
                l = int(length)
                if op == "M":
                    for i in range(l):
                        p = genome_pos + i
                        if p < len(ref):
                            base = seq[offset + i].upper() if offset + i < len(seq) else "N"
                            if p not in pileup:
                                pileup[p] = {"A": 0, "C": 0, "G": 0, "T": 0}
                            depth_by_pos[p] = depth_by_pos.get(p, 0) + 1
                            if base in pileup[p]:
                                pileup[p][base] += 1
                    offset += l
                elif op == "I":
                    offset += l
                elif op == "S":
                    offset += l

    min_depth = 2
    min_alt_freq = 0.2
    variants = []
    for pos in sorted(pileup.keys()):
        counts = pileup[pos]
        depth = depth_by_pos.get(pos, sum(counts.values()))
        if depth < min_depth:
            continue
        ref_base = ref[pos].upper() if pos < len(ref) else "N"
        total = sum(counts.get(b, 0) for b in "ACGT")
        if total == 0:
            continue
        for base in "ACGT":
            if base == ref_base:
                continue
            alt_count = counts.get(base, 0)
            freq = alt_count / total
            if freq >= min_alt_freq:
                variants.append({
                    "pos": pos + 1, "ref": ref_base, "alt": base,
                    "depth": depth, "alt_count": alt_count, "freq": round(freq, 4),
                })

    variants.sort(key=lambda v: -v["freq"])
    variants = variants[:50]

    # Write proper VCF with header
    with open(vcf_path, "w") as f:
        f.write("##fileformat=VCFv4.2\n")
        f.write("##source=ngs-pipeline-python\n")
        f.write(f"##reference={ref_name}\n")
        f.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
        for v in variants:
            f.write(f"{ref_name}\t{v['pos']}\t.\t{v['ref']}\t{v['alt']}\t.\tPASS\tDP={v['depth']};AF={v['freq']}\n")

    return {
        "tool": "python-variant-calling",
        "vcf_path": vcf_path,
        "variants": variants,
        "total_variants": len(variants),
    }


def _parse_vcf(vcf_path: str) -> list[dict]:
    variants = []
    with open(vcf_path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue
            info = {}
            for item in parts[7].split(";"):
                if "=" in item:
                    k, v = item.split("=", 1)
                    info[k] = v
            depth = int(info.get("DP", "0"))
            af = float(info.get("AF", "0"))
            variants.append({
                "pos": int(parts[1]),
                "ref": parts[3],
                "alt": parts[4],
                "depth": depth,
                "alt_count": round(depth * af) if depth else 0,
                "freq": af,
            })
    return variants


# ---------------------------------------------------------------------------
# Step 5: Annotation
# ---------------------------------------------------------------------------

def _run_annotation(vcf_path: str, ref_name: str, tmpdir: str) -> dict:
    annotated_path = os.path.join(tmpdir, "annotated.vcf")
    snpeff = _find_tool("snpeff")

    if snpeff:
        try:
            subprocess.run(
                [snpeff, "ann", ref_name, vcf_path],
                capture_output=True, text=True, timeout=120,
            )
        except Exception as e:
            logger.warning("SnpEff failed, using basic annotation: %s", e)

    return _basic_annotation(vcf_path, ref_name)


KNOWN_VARIANTS = {
    "sars-cov-2": {
        23403: {"gene": "S", "mutation": "D614G", "significance": "Increased transmissibility", "protein_change": "Asp614Gly"},
        28881: {"gene": "N", "mutation": "R203K", "significance": "Common variant", "protein_change": "Arg203Lys"},
        28882: {"gene": "N", "mutation": "G204R", "significance": "Common variant", "protein_change": "Gly204Arg"},
        21563: {"gene": "ORF1ab", "mutation": "P13L", "significance": "Early divergence marker", "protein_change": "Pro13Leu"},
        28883: {"gene": "N", "mutation": "G204R", "significance": "Common variant", "protein_change": "Gly204Arg"},
        26245: {"gene": "ORF1ab", "mutation": "R203K", "significance": "Common in Wuhan-Hu-1", "protein_change": "Arg203Lys"},
        29742: {"gene": "ORF10", "mutation": "G12V", "significance": "Minor variant", "protein_change": "Gly12Val"},
    },
    "lambda": {},
    "ecoli-k12": {},
}


def _basic_annotation(vcf_path: str, ref_name: str) -> dict:
    known = KNOWN_VARIANTS.get(ref_name, {})
    annotations = []

    if os.path.exists(vcf_path):
        with open(vcf_path) as f:
            for line in f:
                if line.startswith("#"):
                    continue
                parts = line.strip().split("\t")
                if len(parts) < 5:
                    continue
                pos = int(parts[1])
                ref_base = parts[3]
                alt_base = parts[4]
                info = {}
                for item in parts[7].split(";") if len(parts) > 7 else []:
                    if "=" in item:
                        k, v = item.split("=", 1)
                        info[k] = v

                annotation = {
                    "pos": pos,
                    "ref": ref_base,
                    "alt": alt_base,
                    "depth": int(info.get("DP", "0")),
                    "freq": float(info.get("AF", "0")),
                    "gene": "unknown",
                    "mutation": f"{ref_base}{pos}{alt_base}",
                    "significance": "Novel variant",
                    "protein_change": "",
                }

                if pos in known:
                    k = known[pos]
                    annotation["gene"] = k["gene"]
                    annotation["mutation"] = k["mutation"]
                    annotation["significance"] = k["significance"]
                    annotation["protein_change"] = k.get("protein_change", "")

                annotations.append(annotation)

    return {
        "tool": "basic-annotation",
        "reference": ref_name,
        "annotations": annotations,
        "total_annotated": len(annotations),
        "known_variants_found": sum(1 for a in annotations if a["significance"] != "Novel variant"),
    }


# ---------------------------------------------------------------------------
# Reference genome download
# ---------------------------------------------------------------------------

async def _download_reference(ref_name: str) -> str:
    url = REFERENCE_URLS.get(ref_name)
    if not url:
        raise ValueError(f"Unknown reference genome: {ref_name}")
    os.makedirs(CACHE_DIR, exist_ok=True)
    fa_path = os.path.join(CACHE_DIR, f"{ref_name}.fa")
    if os.path.exists(fa_path) and os.path.getsize(fa_path) > 0:
        return fa_path
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.content
        if url.endswith(".gz"):
            import gzip
            data = gzip.decompress(data)
        with open(fa_path, "wb") as f:
            f.write(data)
    return fa_path


# ---------------------------------------------------------------------------
# Synthetic FASTQ generator
# ---------------------------------------------------------------------------

def _generate_synthetic_fastq(ref_seq: str, num_reads: int = 500, read_len: int = 100) -> str:
    ref = "".join(line.strip().upper() for line in ref_seq.splitlines() if not line.startswith(">"))
    if len(ref) < read_len:
        ref = ref * ((read_len // len(ref)) + 1)
    lines: list[str] = []
    for i in range(num_reads):
        start = random.randint(0, len(ref) - read_len)
        seq = ref[start:start + read_len]
        mut_rate = 0.01
        seq = "".join(
            random.choice("ACGT") if random.random() < mut_rate else b
            for b in seq
        )
        qual = "".join(chr(33 + min(40, random.randint(20, 40))) for _ in range(read_len))
        lines.append(f"@read{i + 1}")
        lines.append(seq)
        lines.append("+")
        lines.append(qual)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Upload artifacts to Supabase Storage
# ---------------------------------------------------------------------------

def _upload_ngs_files(job_id: str, tmpdir: str, ref_path: str, reference: str) -> dict:
    """Upload BAM, BAI, VCF, and reference FASTA to Supabase Storage.
    Returns dict of URLs keyed by file type."""
    from app.services.artifact_storage import _ensure_bucket, BUCKET, get_client

    _ensure_bucket()
    sb = get_client()
    urls = {}

    files_to_upload = {
        "bam": os.path.join(tmpdir, "sorted.bam"),
        "bai": os.path.join(tmpdir, "sorted.bam.bai"),
        "sam": os.path.join(tmpdir, "aligned.sam"),
        "vcf": os.path.join(tmpdir, "variants.vcf"),
        "reference": ref_path,
    }

    for kind, path in files_to_upload.items():
        if not os.path.exists(path):
            continue
        storage_path = f"{job_id}/{kind}"
        ext = os.path.splitext(path)[1].lower()
        content_types = {
            ".bam": "application/octet-stream",
            ".bai": "application/octet-stream",
            ".sam": "application/octet-stream",
            ".vcf": "text/vcf",
            ".fa": "text/plain",
            ".fasta": "text/plain",
        }
        ct = content_types.get(ext, "application/octet-stream")
        try:
            with open(path, "rb") as f:
                data = f.read()
            sb.storage.from_(BUCKET).upload(
                storage_path, data,
                {"content-type": ct, "upsert": "true"},
            )
            url = sb.storage.from_(BUCKET).get_public_url(storage_path)
            urls[kind] = url
            logger.info("Uploaded NGS artifact: %s -> %s (%d bytes)", kind, url, len(data))
        except Exception as e:
            logger.warning("Failed to upload NGS artifact %s: %s", kind, e)

    return urls


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

class NGSPipeline(BaseTool):
    name = "ngs"

    VALID_DEMO = {"synthetic", "demo", "test"}

    async def run(self, input: dict) -> dict:
        fastq_url = input.get("fastq_url", "").strip()
        reference = input.get("reference", "sars-cov-2").strip().lower()
        job_id = input.get("job_id", "")

        if not fastq_url:
            return {"error": "fastq_url is required"}

        tmpdir = tempfile.mkdtemp(prefix="ngs_")
        steps_completed: list[str] = []
        progress: dict[str, str] = {}

        try:
            # --- Download reference ---
            progress["reference"] = "downloading"
            ref_path = await asyncio.wait_for(_download_reference(reference), timeout=120)
            with open(ref_path) as f:
                ref_content = f.read()

            # --- Prepare FASTQ ---
            fastq_path = os.path.join(tmpdir, "input.fastq")
            trimmed_path = os.path.join(tmpdir, "trimmed.fastq")
            synthetic = fastq_url.lower() in self.VALID_DEMO
            fastq_source = "synthetic"

            if synthetic:
                fastq_data = _generate_synthetic_fastq(ref_content, num_reads=500, read_len=100)
                with open(fastq_path, "w") as f:
                    f.write(fastq_data)
            else:
                fastq_source = "url"
                try:
                    await self._download_fastq(fastq_url, fastq_path)
                except Exception:
                    fastq_source = "synthetic"
                    fastq_data = _generate_synthetic_fastq(ref_content, num_reads=500, read_len=100)
                    with open(fastq_path, "w") as f:
                        f.write(fastq_data)

            # --- Step 1: Quality Control ---
            progress["qc"] = "running"
            qc_report_dir = os.path.join(tmpdir, "qc")
            os.makedirs(qc_report_dir, exist_ok=True)
            qc = await asyncio.to_thread(_run_fastqc, fastq_path, qc_report_dir)
            if isinstance(qc, dict) and "error" in qc:
                return {"error": qc["error"], "step": "qc", "progress": progress}
            steps_completed.append("qc")
            progress["qc"] = "done"

            # --- Step 2: Trimming ---
            progress["trim"] = "running"
            trim_report_dir = os.path.join(tmpdir, "trim")
            os.makedirs(trim_report_dir, exist_ok=True)
            trim_stats = await asyncio.to_thread(_run_fastp, fastq_path, trimmed_path, trim_report_dir)
            if not os.path.exists(trimmed_path):
                shutil.copy2(fastq_path, trimmed_path)
            steps_completed.append("trim")
            progress["trim"] = "done"

            # --- Step 3: Alignment ---
            progress["align"] = "running"
            align_result = await asyncio.to_thread(_run_alignment, trimmed_path, ref_path, tmpdir)
            sam_path = align_result.get("sam_path", os.path.join(tmpdir, "aligned.sam"))
            steps_completed.append("align")
            progress["align"] = "done"

            # --- Step 4: Variant Calling ---
            progress["variants"] = "running"
            variant_result = await asyncio.to_thread(_run_variant_calling, sam_path, ref_path, tmpdir)
            variants = variant_result.get("variants", [])
            vcf_path = variant_result.get("vcf_path", "")
            steps_completed.append("variants")
            progress["variants"] = "done"

            # --- Step 5: Annotation ---
            progress["annotate"] = "running"
            annotation = await asyncio.to_thread(_run_annotation, vcf_path, reference, tmpdir)
            steps_completed.append("annotate")
            progress["annotate"] = "done"

            # --- Step 6: Upload files for visualization ---
            progress["visualization"] = "running"
            file_urls = {}
            if job_id:
                file_urls = await asyncio.to_thread(_upload_ngs_files, job_id, tmpdir, ref_path, reference)
            steps_completed.append("visualization")
            progress["visualization"] = "done"

            # --- Build report ---
            report = _build_report(qc, trim_stats, align_result, variants, annotation, reference)
            consensus = _build_consensus(ref_content, variants)

            return {
                "reference": reference,
                "reference_size": REFERENCE_SIZES.get(reference, 0),
                "fastq_source": fastq_source,
                "qc": qc,
                "trimming": _summarize_trimming(trim_stats),
                "alignment": {
                    "tool": align_result.get("tool", "unknown"),
                    "mapped_reads": align_result.get("mapped_reads", 0),
                    "unmapped_reads": align_result.get("unmapped_reads", 0),
                    "total_alignments": align_result.get("total_alignments", 0),
                },
                "variants": variants[:30],
                "annotation": annotation,
                "report": report,
                "consensus_sequence": f">{reference} consensus (SNVs applied)\n{consensus}",
                "file_urls": file_urls,
                "steps_completed": steps_completed,
                "progress": progress,
                "tools_used": {
                    "qc": qc.get("tool", "unknown"),
                    "trim": trim_stats.get("tool", "unknown"),
                    "align": align_result.get("tool", "unknown"),
                    "variant": variant_result.get("tool", "unknown"),
                    "annotate": annotation.get("tool", "unknown"),
                },
            }

        except ValueError as e:
            return {"error": str(e), "progress": progress}
        except httpx.HTTPStatusError as e:
            return {"error": f"Download failed (HTTP {e.response.status_code})", "progress": progress}
        except asyncio.TimeoutError:
            return {"error": "Pipeline timed out", "progress": progress}
        except Exception as e:
            logger.exception("NGS pipeline failed")
            return {"error": f"Pipeline failed: {e}", "progress": progress}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    async def _download_fastq(self, url: str, dest: str) -> str:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            async with client.stream("GET", url) as r:
                r.raise_for_status()
                with open(dest, "wb") as f:
                    async for chunk in r.aiter_bytes():
                        f.write(chunk)
        return dest


def _summarize_trimming(trim_stats: dict) -> dict:
    before = trim_stats.get("before_filtering", {})
    after = trim_stats.get("after_filtering", {})
    return {
        "tool": trim_stats.get("tool", "unknown"),
        "reads_before": before.get("total_reads", 0),
        "reads_after": after.get("total_reads", 0),
        "reads_discarded": trim_stats.get("filtering_result", {}).get("low_quality_reads", 0),
    }


def _build_consensus(reference_seq: str, variants: list[dict]) -> str:
    ref_lines = reference_seq.splitlines()
    ref = "".join(line.strip().upper() for line in ref_lines if not line.startswith(">"))
    seq = list(ref)
    for v in variants:
        pos = v.get("pos", 0) - 1
        alt = v.get("alt", "")
        if 0 <= pos < len(seq):
            seq[pos] = alt
    return "".join(seq)


def _build_report(qc: dict, trim: dict, align: dict, variants: list[dict], annotation: dict, ref_name: str) -> dict:
    total_variants = len(variants)
    snv_count = sum(1 for v in variants if len(v.get("ref", "")) == 1 and len(v.get("alt", "")) == 1)
    known_count = annotation.get("known_variants_found", 0)
    novel_count = total_variants - known_count

    return {
        "reference": ref_name,
        "steps": ["QC", "Trimming", "Alignment", "Variant Calling", "Annotation", "Visualization"],
        "qc_summary": {
            "total_reads": qc.get("total_reads", 0),
            "total_bases": qc.get("total_bases", 0),
            "mean_quality": qc.get("mean_quality", 0),
            "q30_percent": qc.get("q30_percent", 0),
            "gc_percent": qc.get("gc_percent", 0),
        },
        "trimming_summary": {
            "reads_before": trim.get("reads_before", 0),
            "reads_after": trim.get("reads_after", 0),
        },
        "alignment_summary": {
            "mapped_reads": align.get("mapped_reads", 0),
            "unmapped_reads": align.get("unmapped_reads", 0),
            "mapping_rate": round(
                align.get("mapped_reads", 0) / max(align.get("total_alignments", 1), 1) * 100, 1
            ),
        },
        "variant_summary": {
            "total_variants": total_variants,
            "snv_count": snv_count,
            "known_variants": known_count,
            "novel_variants": novel_count,
        },
    }
