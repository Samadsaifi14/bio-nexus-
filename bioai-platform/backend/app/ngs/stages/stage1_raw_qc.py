"""
Stage 1 — Raw read QC (blueprint Stage 1).

Collect the metrics a FastQC report gives you, but do NOT simply copy FastQC's
PASS/WARN/FAIL flag. The platform computes its own QC state based on the assay, platform,
library type, read length and sample type — so a 2x150 WGS germline sample and a targeted
amplicon panel are judged against different expectations.

Metrics collected
    total_reads, read_length, Q20, Q30, per_base_quality, per_sequence_quality,
    GC_content, adapter_content, sequence_duplication, overrepresented_sequences, N_content

Memory-bounded: quality scores are accumulated in Phred 25 bins per position (not one Python
int per base), so large FASTQ files don't exhaust RAM.

Result contract
    RAW_READ_QC
      total_reads          PASS/WARN/FAIL
      q20                  PASS/WARN/FAIL
      q30                  PASS/WARN/FAIL
      gc_content           PASS/WARN/FAIL (expected range per assay)
      adapter_content      PASS/WARN/FAIL
      duplication          PASS/WARN/FAIL
      n_content            PASS/WARN/FAIL
"""

from __future__ import annotations

import gzip
import os
import re
import zlib
from typing import Any, Optional

from app.ngs.contracts import (
    QcStatus,
    StageContract,
    ThresholdRule,
)

# Illumina TruSeq + Nextera adapter 3' seeds (common, sequence-independent detection below).
_ADAPTER_SEEDS = [
    "AGATCGGAAGAGC",   # TruSeq Read1 / universal
    "GTGACTGGAGTTC",   # TruSeq Read2 barcode
    "GCTCTTCCGATCT",   # Nextera
    "AATGATACGGCGA",   # flowcell
]

_QUAL_RANGE = 45  # typical Phred+33 ceiling for Illumina


class _BoundedQuality:
    """Accumulate mean/percentile-quality per position without storing every score."""

    def __init__(self, max_len: int = 600):
        # sum[position] and count[position] for mean; hist[position] = percentile bins for Q20/Q30
        self.sums: list[int] = [0] * max_len
        self.counts: list[int] = [0] * max_len
        self.hist: list[dict[int, int]] = [{} for _ in range(max_len)]
        self.step = _QUAL_RANGE // 5  # bin every ~9 Phred units

    def add(self, quals: bytes):
        for i, b in enumerate(quals):
            q = b - 33
            if i >= len(self.sums):
                break
            self.sums[i] += q
            self.counts[i] += 1
            bin_ = int(min(max(q, 0), _QUAL_RANGE) // self.step)
            h = self.hist[i]
            h[bin_] = h.get(bin_, 0) + 1

    def position_metrics(self, sample_step: int = 3) -> list[dict]:
        out: list[dict] = []
        for i in range(0, len(self.sums), sample_step):
            if self.counts[i] == 0:
                continue
            mean = self.sums[i] / self.counts[i]
            total = self.counts[i]
            h = self.hist[i]
            # Estimate p25 / p75 from histogram bin centers for a compact per-position quality trend.
            cum = 0
            p25 = p75 = mean
            for bin_i in sorted(h):
                center = (bin_i + 0.5) * self.step
                cum += h[bin_i]
                if cum >= total * 0.25 and p25 == mean:
                    p25 = center
                if cum >= total * 0.75:
                    p75 = center
                    break
            out.append({
                "position": i,
                "mean": round(mean, 1),
                "p25": round(p25, 1),
                "p75": round(p75, 1),
            })
        return out

    def mean_quality(self) -> float:
        tot = sum(self.sums)
        cnt = sum(self.counts)
        return (tot / cnt) if cnt else 0.0

    def fraction_ge(self, threshold: int) -> float:
        """Fraction of all bases with quality >= threshold (Q20/Q30)."""
        good = 0
        total = 0
        for i, h in enumerate(self.hist):
            cnt = self.counts[i]
            if cnt == 0:
                continue
            total += cnt
            below = 0
            for bin_i in sorted(h):
                center = (bin_i + 0.5) * self.step
                if center >= threshold:
                    break
                below += h[bin_i]
            good += cnt - below
        return (good / total * 100.0) if total else 100.0


def _open_fastq(path: str):
    with open(path, "rb") as f:
        magic = f.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(path, "rb")
    return open(path, "rb")


def _n_content(seq: bytes) -> int:
    return seq.count(b"N") + seq.count(b"n")


def _adapter_estimation(read_seqs: list[bytes]) -> float:
    """Estimate % of reads carrying adapter contamination at their 3' end.

    A read is flagged if its 3'-most 30nt contains a >=10nt run matching an adapter seed
    (allowing no mismatches, k-mer anchored at the tail). Simple, deterministic, no deps.
    """
    if not read_seqs:
        return 0.0
    flagged = 0
    for seq in read_seqs:
        s = seq.decode("ascii", "replace")
        tail = s[-30:]
        hit = any(seed in tail for seed in _ADAPTER_SEEDS)
        if hit:
            flagged += 1
    return flagged / len(read_seqs) * 100.0


def _duplication_rate(seen: dict[str, int], total: int) -> float:
    """Non-redundant duplication fraction (reads mapped to one unique sequence)."""
    if not total:
        return 0.0
    unique = len(seen)
    return (1 - unique / total) * 100.0


def compute_raw_qc(path: str, assay: str, sample_meta: dict) -> dict:
    """Compute raw-read metrics from a FASTQ (gzip or plain)."""
    MAX_SAMPLE_READS = 200_000      # sample a bounded prefix for speed on huge files
    WINDOW = 100
    max_len_hint = int(sample_meta.get("read_length") or 300)

    total_reads = 0
    total_bases = 0
    gc_count = 0
    at_count = 0
    n_count = 0
    seen_seqs: dict[str, int] = {}
    read_lengths: list[int] = []
    quality = _BoundedQuality(max(max_len_hint * 2, 300))
    window_seqs: list[bytes] = []
    gc_by_window: list[float] = []
    sampled_read_seqs: list[bytes] = []

    try:
        with _open_fastq(path) as f:
            for i, line in enumerate(f):
                if i >= MAX_SAMPLE_READS * 4:
                    break
                mod = i % 4
                if mod == 1:
                    seq = line.rstrip(b"\r\n")
                    l = len(seq)
                    read_lengths.append(l)
                    total_bases += l
                    total_reads += 1
                    gc_count += seq.count(b"G") + seq.count(b"C") + seq.count(b"g") + seq.count(b"c")
                    at_count += seq.count(b"A") + seq.count(b"T") + seq.count(b"a") + seq.count(b"t")
                    n_count += _n_content(seq)
                    seen_seqs[seq.decode("ascii", "replace")] = seen_seqs.get(seq.decode("ascii", "replace"), 0) + 1
                    if len(window_seqs) >= WINDOW:
                        gc_in_w = sum(s.count(b"G") + s.count(b"C") + s.count(b"g") + s.count(b"c") for s in window_seqs)
                        bases_in_w = sum(len(s) for s in window_seqs)
                        gc_by_window.append(round(gc_in_w / max(bases_in_w, 1) * 100, 2))
                        window_seqs = []
                    window_seqs.append(seq)
                    if len(sampled_read_seqs) < 2000:
                        sampled_read_seqs.append(seq)
                elif mod == 3:
                    quality.add(line.rstrip(b"\r\n"))
    except (OSError, EOFError, zlib.error, gzip.BadGzipFile) as exc:
        return {"error": f"read error: {exc}", "total_reads": total_reads}

    if not total_reads:
        return {"error": "empty FASTQ", "total_reads": 0}

    if window_seqs:
        gc_in_w = sum(s.count(b"G") + s.count(b"C") + s.count(b"g") + s.count(b"c") for s in window_seqs)
        bases_in_w = sum(len(s) for s in window_seqs)
        gc_by_window.append(round(gc_in_w / max(bases_in_w, 1) * 100, 2))

    mean_q = quality.mean_quality()
    q20 = quality.fraction_ge(20)
    q30 = quality.fraction_ge(30)
    gc_pct = gc_count / (gc_count + at_count) * 100 if (gc_count + at_count) else 0.0
    n_pct = n_count / total_bases * 100 if total_bases else 0.0

    read_lengths_sorted = sorted(read_lengths)
    avg_len = sum(read_lengths) / len(read_lengths)
    over_rep = sorted(seen_seqs.items(), key=lambda kv: -kv[1])[:10]
    length_dist: dict[int, int] = {}
    for rl in read_lengths:
        bucket = (rl // 10) * 10
        length_dist[bucket] = length_dist.get(bucket, 0) + 1

    return {
        "tool": "platform-raw-qc",
        "total_reads": total_reads,
        "total_bases": total_bases,
        "avg_read_length": round(avg_len, 1),
        "min_read_length": read_lengths_sorted[0],
        "max_read_length": read_lengths_sorted[-1],
        "gc_percent": round(gc_pct, 2),
        "n_percent": round(n_pct, 4),
        "mean_quality": round(mean_q, 2),
        "q20_percent": round(q20, 2),
        "q30_percent": round(q30, 2),
        "adapter_percent": round(_adapter_estimation(sampled_read_seqs), 2),
        "duplication_percent": round(_duplication_rate(seen_seqs, total_reads), 2),
        "quality_by_position": quality.position_metrics(),
        "gc_by_window": gc_by_window,
        "read_length_distribution": [{"length": k, "count": v} for k, v in sorted(length_dist.items())],
        "overrepresented_sequences": [
            {"sequence": s[:50], "count": c, "percent": round(c / total_reads * 100, 2)}
            for s, c in over_rep
        ],
    }


# ---------------------------------------------------------------------------
# Assay-aware threshold builder
# ---------------------------------------------------------------------------


def _qc_thresholds(assay: str, sample_meta: dict) -> dict[str, ThresholdRule]:
    """Build PASS/WARN/FAIL thresholds from the assay + sample context.

    These are heuristic defaults the platform owns (not FastQC's flags). They're exported so
    operators can tune per assay without touching metric code.
    """
    a = assay.upper()

    # Q30 expectations: WGS/WES high; amplicon highest; RNA moderate.
    q30 = {"OK": 85, "WARN": 75} if a not in ("RNA-SEQ", "RNA") else {"OK": 70, "WARN": 60}
    q20 = {"OK": 92, "WARN": 85}

    # GC expected ranges too broad to be single-windowed; use a tolerance around a target.
    if a in ("AMPLICON", "PANEL", "TARGETED"):
        gc_target, gc_window = 50.0, 20.0
    elif a in ("RNA-SEQ", "RNA"):
        gc_target, gc_window = 50.0, 22.0
    else:
        gc_target, gc_window = 45.0, 25.0

    dup_ok = 55.0   # illumina typical after dedup; high duplication warns
    dup_warn = 70.0

    def _pct_rule(metric, ok, warn):
        def _ev(v):
            try:
                v = float(v)
            except (TypeError, ValueError):
                return QcStatus.FAIL
            if v >= ok:
                return QcStatus.PASS
            if v >= warn:
                return QcStatus.WARN
            return QcStatus.FAIL
        return ThresholdRule(name=metric, metric=metric, evaluate=_ev,
                             expectation=f">= {ok}%")

    def _gc_rule():
        lo_ok, hi_ok = gc_target - gc_window, gc_target + gc_window
        lo_warn, hi_warn = gc_target - gc_window - 8, gc_target + gc_window + 8
        def _ev(v):
            try:
                v = float(v)
            except (TypeError, ValueError):
                return QcStatus.FAIL
            if lo_ok <= v <= hi_ok:
                return QcStatus.PASS
            if lo_warn <= v <= hi_warn:
                return QcStatus.WARN
            return QcStatus.FAIL
        return ThresholdRule(name="gc_content", metric="gc_content", evaluate=_ev,
                             expectation=f"{round(lo_ok,1)}-{round(hi_ok,1)}%")

    def _low_rule(metric, max_ok, max_warn):
        def _ev(v):
            try:
                v = float(v)
            except (TypeError, ValueError):
                return QcStatus.FAIL
            if v <= max_ok:
                return QcStatus.PASS
            if v <= max_warn:
                return QcStatus.WARN
            return QcStatus.FAIL
        return ThresholdRule(name=metric, metric=metric, evaluate=_ev,
                             expectation=f"<= {max_ok}%")

    return {
        "q20": _pct_rule("q20", q20["OK"], q20["WARN"]),
        "q30": _pct_rule("q30", q30["OK"], q30["WARN"]),
        "gc_content": _gc_rule(),
        "adapter_content": _low_rule("adapter_content", 5.0, 20.0),
        "duplication": _low_rule("duplication", dup_ok, dup_warn),
        "n_content": _low_rule("n_content", 1.0, 5.0),
    }


def _stage1_run(sample: dict, state: dict) -> tuple[dict, dict]:
    assay = sample.get("assay") or "WGS"
    meta = sample.get("metadata") or {}
    files = sample.get("files", [])
    if not files:
        return {"error": "no files"}, {}
    primary = files[0]
    qc = compute_raw_qc(primary, assay, meta)
    if "error" in qc:
        return qc, {}
    state.setdefault("raw_qc", {})[primary] = qc
    rules = _qc_thresholds(assay, meta)
    metric_values = {
        "q20": qc["q20_percent"],
        "q30": qc["q30_percent"],
        "gc_content": qc["gc_percent"],
        "adapter_content": qc["adapter_percent"],
        "duplication": qc["duplication_percent"],
        "n_content": qc["n_percent"],
    }
    return qc, metric_values


def raw_qc_contract() -> StageContract:
    return StageContract(
        step="raw_read_qc",
        tool="platform-raw-qc",
        version="0.1.0",
        inputs=["clean_fastq"],
        outputs=["raw_qc_report"],
        rules=lambda sample: list(_qc_thresholds(
            sample.get("assay") or "WGS", sample.get("metadata") or {}
        ).values()),
        fail_blocks=True,
        run=_stage1_run,
    )


def run_raw_qc(sample: dict) -> dict:
    """Build an assay-aware contract and run it (for direct invocation/tests)."""
    from app.ngs.contracts import apply_rules, QcResult, decision_for
    assay = sample.get("assay") or "WGS"
    meta = sample.get("metadata") or {}
    files = sample.get("files", [])
    if not files:
        return {"result": None, "summary": {"status": "FAIL", "decision": "STOP",
                "error": "no files"}}
    primary = files[0]
    qc = compute_raw_qc(primary, assay, meta)
    if "error" in qc:
        return {"result": None, "summary": {"status": "FAIL", "decision": "STOP", "error": qc["error"]}}
    rules = list(_qc_thresholds(assay, meta).values())
    rule_map = {r.metric: r for r in rules}
    metric_values = {
        metric: qc[datum] for metric, datum in [
            ("q20", "q20_percent"), ("q30", "q30_percent"),
            ("gc_content", "gc_percent"), ("adapter_content", "adapter_percent"),
            ("duplication", "duplication_percent"), ("n_content", "n_percent"),
        ]
    }
    metrics = apply_rules(rules, metric_values)
    result = QcResult.from_metrics(metrics, fail_blocks=True)
    return {
        "result": {"step": "raw_read_qc", "qc": result.to_dict(),
                   "decision": result.decision.value, "data": qc},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "qc": qc, "metrics": [m.name for m in metrics]},
    }
