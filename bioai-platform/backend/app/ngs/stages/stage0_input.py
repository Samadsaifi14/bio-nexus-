"""
Stage 0 — Input validation.

Before FastQC, verify the data itself:
    * file existence
    * gzip integrity when the file is actually gzip-compressed
    * FASTQ structure
    * R1/R2 pairing
    * sample names / duplicate uploads
    * optional checksums
    * sequencing metadata

A genuine FAIL here blocks downstream analysis. Plain .fastq files are valid FASTQ inputs;
gzip integrity is therefore N/A (PASS) for uncompressed inputs rather than 0%.
"""

from __future__ import annotations

import gzip
import hashlib
import os
import re
import zlib
from typing import Optional

from app.ngs.contracts import StageContract, ThresholdRule

_QUAL_RE = re.compile(rb"^[!-~]+$")


def validate_gzip(path: str) -> tuple[bool, str]:
    """Check that a .gz input is a valid, decompressible gzip stream."""
    try:
        with open(path, "rb") as fh:
            magic = fh.read(2)
        if magic != b"\x1f\x8b":
            return False, "not gzip (bad magic bytes)"
        with gzip.open(path, "rb") as fh:
            fh.read(65536)
        return True, "gzip OK"
    except (OSError, zlib.error, EOFError) as exc:
        return False, f"gzip error: {exc}"


def _is_fastq_ext(path: str) -> bool:
    return re.search(r"\.(fastq|fq)(\.gz)?$", path, re.IGNORECASE) is not None


def probe_fastq(path: str, n_records: int = 2000) -> dict:
    """Sample the first N records and report structural metrics."""
    out = {
        "records_ok": False,
        "content_lines": 0,
        "max_read_len": 0,
        "min_read_len": 10 ** 9,
        "avg_read_len": 0.0,
        "has_valid_quality": True,
        "phred_range": None,
        "phred_min": None,
        "phred_max": None,
        "read_count_hint": None,
        "first_header": None,
        "is_gzip": False,
    }

    try:
        with open(path, "rb") as raw2:
            header = raw2.read(2)
        out["is_gzip"] = header == b"\x1f\x8b"
        opener = gzip.open(path, "rb") if out["is_gzip"] else open(path, "rb")
        min_q: Optional[int] = None
        max_q: Optional[int] = None
        with opener as raw:
            length_sum = 0
            count = 0
            for i, line in enumerate(raw):
                if i >= n_records * 4:
                    break
                out["content_lines"] = i + 1
                if i % 4 == 0:
                    if not line.startswith(b"@"):
                        out["error"] = f"line {i + 1}: expected '@' header, got {line[:30]!r}"
                        break
                    if i == 0:
                        out["first_header"] = line.decode("utf-8", "replace").strip()
                elif i % 4 == 1:
                    length = len(line.rstrip(b"\r\n"))
                    out["max_read_len"] = max(out["max_read_len"], length)
                    out["min_read_len"] = min(out["min_read_len"], length)
                    length_sum += length
                    count += 1
                elif i % 4 == 2:
                    if not line.startswith(b"+"):
                        out["error"] = f"line {i + 1}: expected '+' separator"
                        break
                elif i % 4 == 3:
                    q = line.rstrip(b"\r\n")
                    if q and _QUAL_RE.match(q) is None:
                        out["has_valid_quality"] = False
                        out["error"] = f"line {i + 1}: invalid quality characters"
                        break
                    if q:
                        vals = [b - 33 for b in q]
                        min_q = min(vals) if min_q is None else min(min_q, min(vals))
                        max_q = max(vals) if max_q is None else max(max_q, max(vals))
            if count:
                out["avg_read_len"] = round(length_sum / count, 1)
            if out["min_read_len"] == 10 ** 9:
                out["min_read_len"] = 0
            out["read_count_hint"] = out["content_lines"] // 4
            out["phred_min"] = min_q
            out["phred_max"] = max_q
            out["phred_range"] = [min_q, max_q] if min_q is not None and max_q is not None else None
            out["records_ok"] = (
                out["content_lines"] > 0
                and out["content_lines"] % 4 == 0
                and "error" not in out
                and out["has_valid_quality"]
            )
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        out["error"] = f"read error: {exc}"
        out["records_ok"] = False
    return out


def checksum_md5(path: str, sample_bytes: int = 1024 * 1024) -> Optional[str]:
    try:
        h = hashlib.md5()
        with open(path, "rb") as fh:
            h.update(fh.read(sample_bytes))
        return h.hexdigest()
    except OSError:
        return None


def _resolve_local_paths(files: list[str]) -> list[str]:
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
    from app.ngs.assays import pair_fastq, sample_id_from_name

    files = _resolve_local_paths(sample.get("files", []))
    metadata = sample.get("metadata") or {}
    data: dict = {"files": [], "pairs": [], "failures": [], "checksums": {}}

    present = 0
    fastq_ok = 0
    compressed_total = 0
    compressed_ok = 0
    exists_total = len(files)

    for f in files:
        rec: dict = {"file": os.path.basename(f)}
        if not os.path.isfile(f):
            data["failures"].append(f"missing file: {f}")
            rec["exists"] = False
            data["files"].append(rec)
            continue

        present += 1
        rec["exists"] = True

        # Gzip validation only applies to compressed inputs. A normal .fastq file must not
        # receive a 0% gzip score simply because it is intentionally uncompressed.
        is_gzip_path = str(f).lower().endswith(".gz")
        rec["compression"] = "gzip" if is_gzip_path else "none"
        if is_gzip_path:
            compressed_total += 1
            gz_ok, gz_msg = validate_gzip(f)
            rec["gzip_ok"] = gz_ok
            rec["gzip_message"] = gz_msg
            if gz_ok:
                compressed_ok += 1
            else:
                data["failures"].append(f"gzip integrity failed: {os.path.basename(f)}")
        else:
            rec["gzip_ok"] = None
            rec["gzip_message"] = "not applicable (uncompressed FASTQ)"

        probe = probe_fastq(f) if _is_fastq_ext(f) else {}
        rec["fastq_ok"] = bool(probe.get("records_ok", False))
        rec["probe"] = probe
        if rec["fastq_ok"]:
            fastq_ok += 1
        else:
            data["failures"].append(f"FASTQ structure failed: {os.path.basename(f)}")

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

    # R1/R2 pairing.
    basenames = [os.path.basename(f) for f in files]
    pairs, singles = pair_fastq(basenames)
    data["pairs"] = [list(p) for p in pairs]
    data["single_reads"] = singles
    pair_ok = not any(("_R2" in s or ".R2" in s) for s in singles)
    if not pair_ok:
        data["failures"].append("orphan R2 file(s) present without a matching R1")

    # Duplicate sample IDs should identify duplicate libraries/uploads, not the normal R1/R2
    # mates of one paired-end library. Count one logical library per resolved pair plus singles.
    logical_inputs: list[str] = [p[0] for p in pairs] + list(singles)
    seen: dict[str, list[str]] = {}
    for name in logical_inputs:
        sid = sample_id_from_name(os.path.basename(name))
        seen.setdefault(sid, []).append(os.path.basename(name))
    dups = {sid: names for sid, names in seen.items() if len(names) > 1}
    if dups:
        data["duplicate_sample_ids"] = dups
        data["failures"].append("duplicate sample id(s) detected: " + ", ".join(dups))

    metric_values = {
        "files_present": (present / exists_total * 100.0) if exists_total else 0.0,
        # No .gz files means the gzip check is N/A, which is a valid PASS state.
        "gzip_integrity": (compressed_ok / compressed_total * 100.0) if compressed_total else 100.0,
        "fastq_structure": (fastq_ok / present * 100.0) if present else 0.0,
        "pairing_integrity": 100.0 if pair_ok else 0.0,
        "checksum_integrity": 100.0 if all(r.get("checksum_match", True) for r in data["files"]) else 0.0,
    }

    meta_ok = True
    meta_msgs = []
    if metadata.get("platform") and metadata.get("read_length"):
        if int(metadata["read_length"]) <= 0:
            meta_ok = False
            meta_msgs.append("invalid read_length")
    if metadata.get("sample_id") is not None and not str(metadata["sample_id"]).strip():
        meta_ok = False
        meta_msgs.append("empty sample_id")
    metric_values["metadata_valid"] = 100.0 if meta_ok else 0.0
    if meta_msgs:
        data["failures"].extend(meta_msgs)

    data["compression_summary"] = {
        "gzip_files": compressed_total,
        "gzip_files_valid": compressed_ok,
        "uncompressed_files": max(present - compressed_total, 0),
    }
    return data, metric_values


def stage0_contract() -> StageContract:
    return StageContract(
        step="input_validation",
        tool="platform-input-validation",
        version="0.1.1",
        inputs=["fastq_files"],
        outputs=["validation_report"],
        rules=[
            ThresholdRule(name="files_present", metric="files_present", evaluate=lambda v: _pct(v, 100, 100)),
            ThresholdRule(name="gzip_integrity", metric="gzip_integrity", evaluate=lambda v: _pct(v, 100, 100)),
            ThresholdRule(name="fastq_structure", metric="fastq_structure", evaluate=lambda v: _pct(v, 100, 100)),
            ThresholdRule(name="pairing_integrity", metric="pairing_integrity", evaluate=lambda v: _worst_ok(v)),
            ThresholdRule(name="metadata_valid", metric="metadata_valid", evaluate=lambda v: _worst_ok(v)),
            ThresholdRule(name="checksum_integrity", metric="checksum_integrity", evaluate=lambda v: _checksum_ok(v)),
        ],
        fail_blocks=True,
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
    return QcStatus.PASS if v >= 100.0 else QcStatus.WARN


def run_input_validation(sample: dict) -> dict:
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
