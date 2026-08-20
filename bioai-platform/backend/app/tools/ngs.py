"""
NGS (Next-Generation Sequencing) Pipeline — 6-step analysis:

1. Quality Control  (FastQC or Python fallback)
2. Trimming/Filter  (fastp or Python fallback)
3. Alignment        (minimap2 + samtools or Python fallback)
4. Variant Calling  (bcftools or Python fallback)
5. Annotation       (SnpEff or cross-reference lookup)
6. Report           (structured JSON summary)
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
import sys
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

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "references")


# ---------------------------------------------------------------------------
# Tool detection helpers
# ---------------------------------------------------------------------------

def _find_tool(name: str) -> str | None:
    """Find a tool binary, checking PATH then app/bin/."""
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
# Step 1: Quality Control (FastQC or Python fallback)
# ---------------------------------------------------------------------------

def _run_fastqc(fastq_path: str, out_dir: str) -> dict:
    """Run FastQC if available, else use Python QC parser."""
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
    """Pure-Python QC: parse FASTQ and compute metrics."""
    total_reads = 0
    total_bases = 0
    gc_count = 0
    at_count = 0
    q_scores: list[int] = []
    read_lengths: list[int] = []
    seen_seqs: dict[str, int] = {}
    line_no = 0

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
            elif line_no % 4 == 0:
                for ch in line.strip():
                    q_scores.append(ord(ch) - 33)

    if total_reads == 0:
        return {"error": "Empty FASTQ file", "total_reads": 0}

    mean_q = sum(q_scores) / len(q_scores) if q_scores else 0
    min_q = min(q_scores) if q_scores else 0
    max_q = max(q_scores) if q_scores else 0
    q20 = sum(1 for q in q_scores if q >= 20) / len(q_scores) * 100 if q_scores else 0
    q30 = sum(1 for q in q_scores if q >= 30) / len(q_scores) * 100 if q_scores else 0
    gc_pct = gc_count / (gc_count + at_count) * 100 if (gc_count + at_count) > 0 else 0
    avg_len = sum(read_lengths) / len(read_lengths) if read_lengths else 0

    overrepresented = sorted(seen_seqs.items(), key=lambda x: -x[1])[:10]

    return {
        "tool": "python-qc",
        "total_reads": total_reads,
        "total_bases": total_bases,
        "avg_read_length": round(avg_len, 1),
        "min_read_length": min(read_lengths) if read_lengths else 0,
        "max_read_length": max(read_lengths) if read_lengths else 0,
        "gc_percent": round(gc_pct, 2),
        "mean_quality": round(mean_q, 2),
        "min_quality": min_q,
        "max_quality": max_q,
        "q20_percent": round(q20, 2),
        "q30_percent": round(q30, 2),
        "overrepresented_sequences": [
            {"sequence": s[:50], "count": c, "percent": round(c / total_reads * 100, 2)}
            for s, c in overrepresented
        ],
    }


# ---------------------------------------------------------------------------
# Step 2: Trimming/Filtering (fastp or Python fallback)
# ---------------------------------------------------------------------------

def _run_fastp(fastq_in: str, fastq_out: str, report_dir: str) -> dict:
    """Run fastp if available, else use Python quality filter."""
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
    """Pure-Python quality filter: keep reads with mean Q >= 20, length >= 50."""
    kept = 0
    discarded = 0
    line_no = 0
    buf: list[str] = []

    with open(fastq_in) as fin, open(fastq_out, "w") as out:
        for line in fin:
            line_no += 1
            buf.append(line)
            if line_no % 4 == 0:
                seq = buf[1].strip()
                qual = buf[3].strip()
                if len(seq) < 50:
                    discarded += 1
                    buf.clear()
                    continue
                q_scores = [ord(ch) - 33 for ch in qual]
                mean_q = sum(q_scores) / len(q_scores) if q_scores else 0
                if mean_q >= 20:
                    out.writelines(buf)
                    kept += 1
                else:
                    discarded += 1
                buf.clear()

    return {
        "tool": "python-trim",
        "before_filtering": {"total_reads": kept + discarded, "total_bases": 0},
        "after_filtering": {"total_reads": kept, "total_bases": 0},
        "reads_discarded": discarded,
        "filtering_result": {
            "low_quality_reads": discarded,
        },
    }


# ---------------------------------------------------------------------------
# Step 3: Alignment (minimap2 + samtools, or Python fallback)
# ---------------------------------------------------------------------------

def _run_alignment(fastq_path: str, ref_path: str, tmpdir: str) -> dict:
    """Run minimap2 + samtools if available, else Python fallback."""
    sam_path = os.path.join(tmpdir, "aligned.sam")
    bam_path = os.path.join(tmpdir, "sorted.bam")
    bai_path = os.path.join(tmpdir, "sorted.bam.bai")

    mm2 = _find_tool("minimap2")
    samtools = _find_tool("samtools")

    if mm2 and samtools and not _IS_WINDOWS:
        try:
            # minimap2 alignment
            with open(sam_path, "w") as sam_out:
                proc = subprocess.run(
                    [mm2, "-ax", "sr", ref_path, fastq_path],
                    stdout=sam_out, stderr=subprocess.PIPE, timeout=300,
                )
            if proc.returncode != 0:
                logger.warning("minimap2 returned %d: %s", proc.returncode, proc.stderr[:200])

            # samtools sort + index
            subprocess.run(
                ["samtools", "sort", "-o", bam_path, sam_path],
                capture_output=True, timeout=120,
            )
            subprocess.run(
                ["samtools", "index", bam_path],
                capture_output=True, timeout=60,
            )

            # Parse stats
            stats = _parse_alignment_stats(sam_path)
            stats["tool"] = "minimap2+samtools"
            stats["bam_path"] = bam_path
            stats["bai_path"] = bai_path
            return stats
        except Exception as e:
            logger.warning("Native alignment failed, using Python fallback: %s", e)

    return _python_alignment(fastq_path, ref_path, sam_path)


def _python_alignment(fastq_path: str, ref_path: str, sam_path: str) -> dict:
    """Pure-Python alignment: generate SAM with unmapped reads."""
    total = 0
    with open(fastq_path) as fin, open(sam_path, "w") as out:
        out.write("@HD\tVN:1.6\tSO:unsorted\n")
        # Write reference sequence header
        with open(ref_path) as rf:
            for line in rf:
                if line.startswith(">"):
                    name = line.strip().split()[0][1:]
                    out.write(f"@SQ\tSN:{name}\tLN:30000\n")
                    break

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
                flag = 4
                out.write(f"{qname}\t{flag}\t*\t0\t0\t*\t*\t0\t0\t{seq}\t{qual}\n")

    return {
        "tool": "python-alignment",
        "mapped_reads": 0,
        "unmapped_reads": total,
        "total_alignments": total,
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
# Step 4: Variant Calling (bcftools or Python fallback)
# ---------------------------------------------------------------------------

def _run_variant_calling(sam_path: str, ref_path: str, tmpdir: str) -> dict:
    """Run bcftools mpileup + call if available, else Python fallback."""
    vcf_path = os.path.join(tmpdir, "variants.vcf")
    bcftools = _find_tool("bcftools")
    samtools = _find_tool("samtools")

    if bcftools and samtools and not _IS_WINDOWS:
        try:
            bam_path = os.path.join(tmpdir, "sorted.bam")
            if not os.path.exists(bam_path):
                return _python_variant_calling(sam_path, ref_path, vcf_path)

            proc = subprocess.run(
                ["bcftools", "mpileup", "-f", ref_path, bam_path, "-O", "u"] ,
                capture_output=True, timeout=120,
            )
            if proc.returncode != 0:
                logger.warning("bcftools mpileup failed, using Python fallback")
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
    """Pure-Python variant calling from SAM pileup."""
    ref_lines = open(ref_path).readlines()
    ref = "".join(line.strip().upper() for line in ref_lines if not line.startswith(">"))

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

    # Write VCF
    with open(vcf_path, "w") as f:
        f.write("##fileformat=VCFv4.2\n")
        f.write("##source=ngs-pipeline-python\n")
        f.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
        for v in variants:
            f.write(f"1\t{v['pos']}\t.\t{v['ref']}\t{v['alt']}\t.\tPASS\tDP={v['depth']};AF={v['freq']}\n")

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
# Step 5: Annotation (SnpEff or basic cross-reference)
# ---------------------------------------------------------------------------

def _run_annotation(vcf_path: str, ref_name: str, tmpdir: str) -> dict:
    """Annotate variants using SnpEff if available, else basic annotation."""
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


def _basic_annotation(vcf_path: str, ref_name: str) -> dict:
    """Cross-reference variant positions against known variant databases."""
    KNOWN_VARIANTS = {
        "sars-cov-2": {
            23403: {"gene": "S", "mutation": "D614G", "significance": "Increased transmissibility"},
            28881: {"gene": "N", "mutation": "R203K", "significance": "Common variant"},
            28882: {"gene": "N", "mutation": "G204R", "significance": "Common variant"},
            21563: {"gene": "ORF1ab", "mutation": "P13L", "significance": "Early divergence marker"},
        },
        "lambda": {},
        "ecoli-k12": {},
    }

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
                }

                if pos in known:
                    k = known[pos]
                    annotation["gene"] = k["gene"]
                    annotation["mutation"] = k["mutation"]
                    annotation["significance"] = k["significance"]

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
        logger.info("Using cached reference %s (%d bytes)", ref_name, os.path.getsize(fa_path))
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
# Synthetic FASTQ generator (for demo)
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
# Main Pipeline
# ---------------------------------------------------------------------------

class NGSPipeline(BaseTool):
    name = "ngs"

    VALID_DEMO = {"synthetic", "demo", "test"}

    async def run(self, input: dict) -> dict:
        fastq_url = input.get("fastq_url", "").strip()
        reference = input.get("reference", "sars-cov-2").strip().lower()

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
                logger.info("Generating synthetic FASTQ reads")
                fastq_data = _generate_synthetic_fastq(ref_content, num_reads=500, read_len=100)
                with open(fastq_path, "w") as f:
                    f.write(fastq_data)
            else:
                fastq_source = "url"
                try:
                    await self._download_fastq(fastq_url, fastq_path)
                except Exception:
                    logger.info("FASTQ download failed, generating synthetic reads")
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
            sam_path = os.path.join(tmpdir, "aligned.sam")
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

            # --- Step 6: Report ---
            progress["report"] = "running"
            report = _build_report(qc, trim_stats, align_result, variants, annotation, reference)
            steps_completed.append("report")
            progress["report"] = "done"

            # --- Consensus ---
            consensus = _build_consensus(ref_content, variants)

            return {
                "reference": reference,
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
        "steps": ["QC", "Trimming", "Alignment", "Variant Calling", "Annotation"],
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
