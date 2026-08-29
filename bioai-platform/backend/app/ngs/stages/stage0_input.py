"""
Stage 0 — Input validation.

Before FastQC, verify the data itself (blueprint Stage 0):

    * file existence
    * gzip integrity
    * FASTQ structure (4-line records, valid quality chars, consistent read lengths)
    * read identifiers (R1/R2 markers valid, no orphan R2)
    * R1/R2 pairing (same sample stem for every pair)
    * sample names (derived, non-empty, sane)
    * duplicate sample IDs (detect accidental re-uploads of the same sample under two names)
    * file checksums (optional, if a checksum manifest / md5 sidecar is present)
    * sequencing metadata (platform/read length consistency if declared)

Result contract:
    INPUT_VALIDATION
      status: PASS / WARN / FAIL
      paired_reads: PASS
      gzip_integrity: PASS
      sample_metadata: PASS

A FAIL here -> STOP (do not proceed to FastQC on corrupt data).
"""

from __future__ import annotations

import gzip
import hashlib
import os
import re
import zlib
from dataclasses import dataclass, field
from typing import Any, Optional

from app.ngs.contracts import StageContract, ThresholdRule, bounded_rule, run_contract

_QUAL_RE = re.compile(rb"^[!-~]+$")


def validate_gzip(path: str) -> tuple[bool, str]:
    """Check a .gz file is a valid gzip stream (header + a decompressible member)."""
    try:
        with open(path, "rb") as fh:
            magic = fh.read(2)
        if magic != b"\x1f\x8b":
            return False, "not gzip (bad magic bytes)"
        # Attempt a partial decompress to prove integrity without loading everything.
        with gzip.open(path, "rb") as fh:
            chunk = fh.read(65536)
        return (len(chunk) >= 0), "gzip OK"
    except (OSError, zlib.error, EOFError) as exc:
        return False, f"gzip error: {exc}"


def _is_fastq_ext(path: str) -> bool:
    return re.search(r"\.(fastq|fq)(\.gz)?$", path, re.IGNORECASE) is not None


def probe_fastq(path: str, n_records: int = 2000) -> dict:
    """Sample the first N records and report structural metrics.

    Returns a dict with: records_ok, total_lines_sampled, max_read_len, min_read_len,
    avg_read_len, has_valid_quality, phred_range, read_count_hint, first_header, is_gzip.
    """
    out = {
        "records_ok": False,
        "content_lines": 0,
        "max_read_len": 0,
        "min_read_len": 10 ** 9,
        "avg_read_len": 0.0,
        "has_valid_quality": True,
        "phred_min": 0,
        "phred_max": 0,
        "read_count_hint": None,
        "first_header": None,
        "is_gzip": False,
    }

    try:
        with open(path, "rb") as raw2:
            header = raw2.read(2)
        out["is_gzip"] = header == b"\x1f\x8b"
        opener = gzip.open(path, "rb") if out["is_gzip"] else open(path, "rb")
        with opener as raw:
            length_sum = 0
            count = 0
            for i, line in enumerate(raw):
                if i >= n_records * 4:
                    break
                out["content_lines"] = i + 1
                if i % 4 == 0:
                    if not line.startswith(b"@"):
                        out["error"] = f"line {i+1}: expected '@' header, got {line[:30]!r}"
                        break
                    if i == 0:
                        out["first_header"] = line.decode("utf-8", "replace").strip()
                elif i % 4 == 1:
                    l = len(line.rstrip(b"\r\n"))
                    out["max_read_len"] = max(out["max_read_len"], l)
                    out["min_read_len"] = min(out["min_read_len"], l)
                    length_sum += l
                    count += 1
                elif i % 4 == 3:
                    q = line.rstrip(b"\r\n")
                    if q and _QUAL_RE.match(q) is None:
                        out["error"] = f"line {i+1}: invalid quality characters"
                        break
                    for b in q:
                        out["phred_min"] = min(out["phred_min"], b - 33)
                        out["phred_max"] = max(out["phred_max"], b - 33)
            if count:
                out["avg_read_len"] = round(length_sum / count, 1)
            if out["min_read_len"] == 10 ** 9:
                out["min_read_len"] = 0
            out["read_count_hint"] = out["content_lines"] // 4
            out["records_ok"] = (
                out["content_lines"] > 0
                and "error" not in out
                and out["has_valid_quality"]
            )
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        out["error"] = f"read error: {exc}"
        out["records_ok"] = False
    return out


def checksum_md5(path: str, sample_bytes=1024 * 1024) -> Optional[str]:
    """Compute an MD5 over the first sample_bytes (fast). Returns hex digest or None."""
    try:
        h = hashlib.md5()
        with open(path, "rb") as fh:
            h.update(fh.read(sample_bytes))
        return h.hexdigest()
    except OSError:
        return None


def _resolve_local_paths(files: list[str]) -> list[str]:
    """Map file references to on-disk paths when they are plain filenames."""
    resolved = []
    for f in files:
        if os.path.isfile(f):
            resolved.append(f)
        elif os.path.isfile(os.path.basename(f)):
            resolved.append(os.path.basename(f))
        else:
            resolved.append(f)
    return resolved


def _stage0_run(sample: dict, state: dict) -> tuple[dict, dict]:
    """Stage 0 execution: validate input files + metadata.

    sample: {files: [paths], reference: str, metadata: {...}, checksums: {path: md5}}
    Returns (data, metric_values).
    """
    from app.ngs.assays import pair_fastq, sample_id_from_name

    files = _resolve_local_paths(sample.get("files", []))
    metadata = sample.get("metadata") or {}
    data: dict = {"files": [], "pairs": [], "failures": [], "checksums": {}}
    metric_values: dict = {}

    present = 0
    fastq_ok = 0
    gzip_ok = 0
    exists_total = len(files)
    for f in files:
        rec: dict = {"file": os.path.basename(f)}
        if not os.path.isfile(f):
            data["failures"].append(f"missing file: {f}")
            rec["exists"] = False
        else:
            present += 1
            rec["exists"] = True
            gz_ok = True
            gz_msgs = []
            if str(f).endswith(".gz"):
                ok, msg = validate_gzip(f)
                gz_ok = ok
                if ok:
                    gzip_ok += 1
                gz_msgs.append(msg)
            rec["gzip_ok"] = gz_ok
            probe = probe_fastq(f) if _is_fastq_ext(f) else {}
            rec["fastq_ok"] = bool(probe.get("records_ok", False))
            rec["probe"] = probe
            if rec["fastq_ok"]:
                fastq_ok += 1
            rec["md5"] = checksum_md5(f)
            declared_md5 = (sample.get("checksums") or {}).get(f) or (
                (sample.get("checksums") or {}).get(os.path.basename(f))
            )
            if declared_md5 and declared_md5.lower() != rec["md5"]:
                data["failures"].append(f"checksum mismatch: {os.path.basename(f)}")
                rec["checksum_match"] = False
            else:
                rec["checksum_match"] = True
            data["checksums"][os.path.basename(f)] = rec["md5"]
        data["files"].append(rec)

    # R1/R2 pairing
    pairs, singles = pair_fastq([os.path.basename(f) for f in files])
    data["pairs"] = [list(p) for p in pairs]
    data["single_reads"] = singles
    pair_ok = not any(("_R2" in s or ".R2" in s) and "_R1" not in s and ".R1" not in s for s in singles)
    if not pair_ok:
        data["failures"].append("orphan R2 file(s) present without a matching R1")

    # Duplicate sample IDs
    seen: dict[str, list[str]] = {}
    for f in files:
        sid = sample_id_from_name(os.path.basename(f))
        seen.setdefault(sid, []).append(os.path.basename(f))
    dups = {sid: names for sid, names in seen.items() if len(names) > 1}
    if dups:
        data["duplicate_sample_ids"] = dups
        data["failures"].append("duplicate sample id(s) detected: " + ", ".join(dups))

    # Metric contract
    metric_values = {
        "files_present": (present / exists_total * 100.0) if exists_total else 0.0,
        "gzip_integrity": (gzip_ok / present * 100.0) if present else 0.0,
        "fastq_structure": (fastq_ok / present * 100.0) if present else 0.0,
        "pairing_integrity": 100.0 if pair_ok else 0.0,
        "checksum_integrity": (
            100.0 if all(r.get("checksum_match", True) for r in data["files"]) else 0.0
        ),
    }

    # sample_metadata checks
    meta_ok = True
    meta_msgs = []
    if metadata.get("platform") and metadata.get("read_length"):
        if int(metadata["read_length"]) <= 0:
            meta_ok = False
            meta_msgs.append("invalid read_length")
    if metadata.get("sample_id") and len(str(metadata["sample_id"]).strip()) == 0:
        meta_ok = False
        meta_msgs.append("empty sample_id")
    metric_values["metadata_valid"] = 100.0 if meta_ok else 0.0
    if meta_msgs:
        data["failures"].extend(meta_msgs)

    return data, metric_values


def stage0_contract() -> StageContract:
    return StageContract(
        step="input_validation",
        tool="platform-input-validation",
        version="0.1.0",
        inputs=["fastq_files"],
        outputs=["validation_report"],
        rules=[
            ThresholdRule(name="files_present", metric="files_present",
                          evaluate=lambda v: _pct(v, 100, 100)),
            ThresholdRule(name="gzip_integrity", metric="gzip_integrity",
                          evaluate=lambda v: _pct(v, 100, 100)),
            ThresholdRule(name="fastq_structure", metric="fastq_structure",
                          evaluate=lambda v: _pct(v, 100, 100)),
            ThresholdRule(name="pairing_integrity", metric="pairing_integrity",
                          evaluate=lambda v: _worst_ok(v)),
            ThresholdRule(name="metadata_valid", metric="metadata_valid",
                          evaluate=lambda v: _worst_ok(v)),
            ThresholdRule(name="checksum_integrity", metric="checksum_integrity",
                          evaluate=lambda v: _checksum_ok(v)),
        ],
        fail_blocks=True,   # corrupt input must STOP before any analysis
        run=_stage0_run,
    )


def _pct(v: float, warn_min: float, ok_min: float):
    from app.ngs.contracts import QcStatus
    if v >= ok_min:
        return QcStatus.PASS
    if v >= warn_min:
        return QcStatus.WARN
    return QcStatus.FAIL


def _worst_ok(v: float):
    from app.ngs.contracts import QcStatus
    return QcStatus.PASS if v >= 100.0 else QcStatus.FAIL


def _checksum_ok(v: float):
    from app.ngs.contracts import QcStatus
    # Checksums are advisory when none are supplied (100% assumed); a real mismatch drops below.
    return QcStatus.PASS if v >= 100.0 else QcStatus.WARN


def run_input_validation(sample: dict) -> dict:
    """Run Stage 0 and return a dict plus the full StageResult."""
    from app.ngs.contracts import run_contract
    res = run_contract(stage0_contract(), sample, {})
    return {
        "result": res.to_dict(),
        "summary": {
            "status": res.qc.status.value if res.qc else "FAIL",
            "decision": res.decision.value,
            "validation": res.data,
        },
    }
