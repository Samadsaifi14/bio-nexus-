"""
Stage 3 — Read preprocessing (blueprint Stage 3).

Do NOT automatically run adapter trimming, UMI extraction and quality trimming for every
sample. The orchestrator decides from metadata + observed data:

    Adapters present?            -> adapter trimming
    UMIs declared?               -> UMI extraction
    Poor-quality 3' tails?       -> quality trimming

It then reports:
    raw reads, retained reads, discarded reads, adapter removal, mean read quality, Q30,
    read length after trimming
and detects:
    > X% reads lost, excessive adapter contamination, severe quality degradation

Pure-Python fallback (the dev environment has no fastp/cutadapt), but the plan/contract
drives it so swapping in fastp later is a like-for-like replacement.
"""

from __future__ import annotations

import gzip
import os
import re
import zlib
from typing import Any, Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule

_ADAPTERS = ["AGATCGGAAGAGC", "GTGACTGGAGTTC", "GCTCTTCCGATCT", "AATGATACGGCGA"]


# ---------------------------------------------------------------------------
# Preprocessing plan (the "smart choice" the blueprint calls for)
# ---------------------------------------------------------------------------


def plan_preprocessing(meta: dict, qc: Optional[dict]) -> dict:
    """Choose which preprocessing steps to run based on metadata + observed data.

    Returns a plan dict. The plan is deterministic and auditable (each choice carries a
    reason), matching the blueprint's "workflow engine should choose based on metadata".
    """
    plan: dict = {
        "adapter_trim": False,
        "umi_extraction": False,
        "quality_trim": False,
        "min_qual": int(meta.get("min_quality") or 20),
        "min_len": int(meta.get("min_length") or 30),
        "reasons": [],
    }

    # Adapter trimming: declared OR observed adapter contamination in the raw QC.
    declared_adapter = str(meta.get("adapters") or meta.get("adapter") or "").lower()
    if declared_adapter in ("yes", "true", "1", "trim", "auto"):
        plan["adapter_trim"] = True
        plan["reasons"].append("adapter trimming declared in metadata")
    elif qc and qc.get("adapter_percent", 0) > 5.0:
        plan["adapter_trim"] = True
        plan["reasons"].append(f"adapter contamination {qc.get('adapter_percent')}% observed in raw QC")

    # UMI extraction.
    if str(meta.get("umi") or "").lower() in ("yes", "true", "1", "extract"):
        plan["umi_extraction"] = True
        plan["reasons"].append("UMI extraction declared in metadata")

    # Quality trimming.
    if str(meta.get("quality_trim") or "").lower() in ("yes", "true", "1", "auto"):
        plan["quality_trim"] = True
        plan["reasons"].append("quality trimming declared in metadata")
    elif (meta.get("quality_trim", "auto").lower() == "auto"
          and qc and qc.get("mean_quality", 40) < 35):
        plan["quality_trim"] = True
        plan["reasons"].append("low mean quality in raw QC -> trim 3' tails")

    if not plan["adapter_trim"] and not plan["umi_extraction"] and not plan["quality_trim"]:
        plan["reasons"].append("no preprocessing steps required for this sample")

    return plan


# ---------------------------------------------------------------------------
# Trimming primitives
# ---------------------------------------------------------------------------


def _trim_quality_tail(seq: str, qual: str, min_qual: int) -> tuple[str, str]:
    """Trim low-quality bases from the 3' end (simple quality-tail trim)."""
    qvals = [ord(c) - 33 for c in qual]
    cutoff = len(seq)
    # find last index where sliding-window mean >= min_qual near the end
    window = 5
    mean = 0.0
    # Walk from the end inward; trim a run whose average quality < min_qual.
    # Simple approach: find longest suffix with mean quality below threshold, cut it.
    suffix_sum = 0
    suffix_len = 0
    best_cut = len(seq)
    for i in range(len(seq) - 1, -1, -1):
        suffix_sum += qvals[i]
        suffix_len += 1
        win = qvals[max(i, i - window + 1): i + 1]
        meanw = sum(win) / len(win)
        if meanw < min_qual:
            best_cut = i  # tentative: clip from here
            # don't break early; keep scanning for longer bad runs
        else:
            break
    if best_cut < len(seq):
        seq = seq[:best_cut]
        qual = qual[:best_cut]
    return seq, qual


def _remove_adapter(seq: str, qual: str) -> tuple[str, str, bool]:
    """Detect an adapter seed in the 3' tail and truncate the read there."""
    tail = seq[-30:]
    for ad in _ADAPTERS:
        idx = tail.find(ad)
        if idx >= 0:
            cut = len(seq) - len(tail) + idx
            return seq[:cut], qual[:cut], True
    return seq, qual, False


_UMI_NAME_RE = re.compile(r"[:._-]([ACGTN]{4,12})(?=[:._-]|$)")


def trim_read(header: str, seq: str, qual: str, plan: dict) -> tuple[Optional[str], dict]:
    """Apply the plan to a single read. Returns (fastq_lines_or_None, stats)."""
    stats = {"adapter_removed": False, "umi_extracted": None, "discarded": False}

    if plan.get("umi_extraction"):
        # UMI commonly at the 5' of the sequence or embedded in the header after the run id.
        # Simple: if header has a barcode/umi segment, record it; keep read as-is otherwise.
        m = _UMI_NAME_RE.search(header)
        if m:
            stats["umi_extracted"] = m.group(1)

    if plan.get("adapter_trim"):
        seq, qual, hit = _remove_adapter(seq, qual)
        stats["adapter_removed"] = hit

    if plan.get("quality_trim"):
        seq, qual = _trim_quality_tail(seq, qual, plan.get("min_qual", 20))

    if len(seq) < plan.get("min_len", 30):
        stats["discarded"] = True
        return None, stats

    return f"{header}\n{seq}\n+\n{qual}\n", stats


def preprocess_fastq(
    path: str,
    out_dir: str,
    plan: dict,
    sample_name: str = "",
    max_reads: Optional[int] = None,
) -> dict:
    """Stream a FASTQ through the plan, writing a trimmed FASTQ, and collect stats."""
    basename = os.path.basename(path)
    out_path = os.path.join(out_dir, sample_name or basename)
    if out_path.endswith(".gz"):
        out_path = out_path[:-3] + ".clean.fastq.gz"
    else:
        out_path = out_path + ".clean.fastq.gz"

    raw_reads = retained = discarded = adapter_removed = 0
    length_sum = 0
    q_scores: list[int] = []
    umis: list[str] = []

    with open(path, "rb") as f:
        magic = f.read(2)
    opener = gzip.open(path, "rb") if magic == b"\x1f\x8b" else open(path, "rb")

    try:
        with opener as src, gzip.open(out_path, "wt", encoding="ascii") as dst:
            buf: list[str] = []
            count = 0
            for i, line in enumerate(src):
                if max_reads is not None and raw_reads >= max_reads:
                    break
                buf.append(line.decode("ascii", "replace").rstrip("\n"))
                if len(buf) == 4:
                    raw_reads += 1
                    header, seq, _, qual = buf
                    res = trim_read(header, seq, qual, plan)
                    if res and res[0] is not None:
                        retained += 1
                        dst.write(res[0])
                        length_sum += len(seq)
                        for ch in res[0].split("\n")[3]:
                            q_scores.append(ord(ch) - 33)
                    else:
                        discarded += 1
                    if res and res[1].get("adapter_removed"):
                        adapter_removed += 1
                    if res and res[1].get("umi_extracted"):
                        umis.append(res[1]["umi_extracted"])
                    buf = []
            if buf and len(buf) == 4:  # trailing partial record
                raw_reads += 1
                discarded += 1
    except (OSError, EOFError, zlib.error, gzip.BadGzipFile) as exc:
        return {"error": f"read error: {exc}"}

    avg_len = (length_sum / retained) if retained else 0.0
    q20 = sum(1 for q in q_scores if q >= 20) / len(q_scores) * 100 if q_scores else 0
    q30 = sum(1 for q in q_scores if q >= 30) / len(q_scores) * 100 if q_scores else 0
    mean_q = sum(q_scores) / len(q_scores) if q_scores else 0.0

    return {
        "tool": "platform-preprocess",
        "raw_reads": raw_reads,
        "retained_reads": retained,
        "discarded_reads": discarded,
        "read_loss_percent": round((discarded / raw_reads * 100.0) if raw_reads else 0.0, 2),
        "adapter_removed_reads": adapter_removed,
        "mean_quality_after": round(mean_q, 2),
        "q20_after": round(q20, 2),
        "q30_after": round(q30, 2),
        "avg_read_length_after": round(avg_len, 1),
        "umis_extracted": len(umis),
        "out_path": out_path,
        "plan": plan,
    }


def _stage3_run(sample: dict, state: dict) -> tuple[dict, dict]:
    meta = sample.get("metadata") or {}
    files = sample.get("files", [])
    if not files:
        return {"error": "no files"}, {}
    raw_qc = (state.get("raw_qc") or {}).get(files[0]) or {}
    plan = plan_preprocessing(meta, raw_qc)
    out_dir = meta.get("out_dir") or os.path.join(sample.get("workdir", ""), "clean")
    os.makedirs(out_dir, exist_ok=True)
    stats = preprocess_fastq(files[0], out_dir, plan, sample_name=sample.get("sample_id", ""))
    if "error" in stats:
        return stats, {}
    state.setdefault("clean_fastq", {})[files[0]] = stats["out_path"]
    return stats, {
        "read_retention": (100.0 - stats["read_loss_percent"]),
        "quality_after": stats["mean_quality_after"],
        "adapter_removed": stats["adapter_removed_reads"],
    }


def stage3_contract() -> StageContract:
    return StageContract(
        step="preprocessing",
        tool="platform-preprocess",
        version="0.1.0",
        inputs=["raw_fastq (validated)", "raw_qc"],
        outputs=["clean_fastq", "preprocess_stats"],
        rules=[
            ThresholdRule(name="read_retention", metric="read_retention",
                          evaluate=lambda v: _retention_rule(v)),
            ThresholdRule(name="quality_after", metric="quality_after",
                          evaluate=lambda v: _quality_rule(v)),
        ],
        fail_blocks=True,
        run=_stage3_run,
    )


def _retention_rule(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return QcStatus.FAIL
    if v >= 85.0:
        return QcStatus.PASS
    if v >= 70.0:
        return QcStatus.WARN
    return QcStatus.FAIL   # > ~15-30% reads lost


def _quality_rule(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return QcStatus.FAIL
    if v >= 30.0:
        return QcStatus.PASS
    if v >= 20.0:
        return QcStatus.WARN
    return QcStatus.FAIL   # severe quality degradation


def run_preprocessing(sample: dict) -> dict:
    contract = stage3_contract()
    from app.ngs.contracts import apply_rules, QcResult
    meta = sample.get("metadata") or {}
    files = sample.get("files", [])
    if not files:
        return {"summary": {"status": "FAIL", "decision": "STOP", "error": "no files"}}
    plan = plan_preprocessing(meta, sample.get("raw_qc"))
    out_dir = meta.get("out_dir") or os.path.join(sample.get("workdir", ""), "clean")
    os.makedirs(out_dir, exist_ok=True)
    stats = preprocess_fastq(files[0], out_dir, plan, sample_name=sample.get("sample_id", ""))
    if "error" in stats:
        return {"summary": {"status": "FAIL", "decision": "STOP", "error": stats["error"]}}
    metric_values = {
        "read_retention": 100.0 - stats["read_loss_percent"],
        "quality_after": stats["mean_quality_after"],
    }
    metrics = apply_rules(contract.resolve_rules(sample), metric_values)
    result = QcResult.from_metrics(metrics, fail_blocks=True)
    return {
        "result": {"step": "preprocessing", "qc": result.to_dict(),
                   "decision": result.decision.value, "data": stats},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "stats": stats, "plan": plan},
    }
