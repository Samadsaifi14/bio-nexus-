"""Local MAFFT multiple-sequence-alignment wrapper.

The wrapper invokes a locally installed MAFFT binary and validates the returned
alignment before exposing it to the rest of BioNexus.  Strategy flags follow
the MAFFT v7 command-line definitions; output must preserve every input record
and residue exactly once.  An unavailable, failed, or malformed MAFFT result is
reported as ``None`` so the calling pipeline can use its explicitly labelled
fallback path.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

_MAFFT_BIN: str | None = None
_MAFFT_VERSION: str | None = None

# Canonical MAFFT v7 strategy definitions.  E-INS-i uses generalized affine
# pairwise alignment (--genafpair); --epg is not an E-INS-i strategy switch.
STRATEGY_FLAGS: dict[str, list[str]] = {
    "auto": ["--auto"],
    "fft-ns-2": ["--retree", "2", "--maxiterate", "0"],
    "fft-ns-i": ["--maxiterate", "1000"],
    "l-ins-i": ["--localpair", "--maxiterate", "1000"],
    "g-ins-i": ["--globalpair", "--maxiterate", "1000"],
    "e-ins-i": ["--genafpair", "--maxiterate", "1000"],
}


def _ensure_mafft() -> str | None:
    """Locate the local MAFFT binary. Returns None if unavailable."""
    global _MAFFT_BIN
    if _MAFFT_BIN and os.path.isfile(_MAFFT_BIN):
        return _MAFFT_BIN

    for candidate in [
        "/usr/local/bin/mafft",
        shutil.which("mafft") or "",
    ]:
        if candidate and os.path.isfile(candidate):
            _MAFFT_BIN = candidate
            return _MAFFT_BIN

    return None


def _mafft_version(mafft_bin: str) -> str | None:
    global _MAFFT_VERSION
    if _MAFFT_VERSION:
        return _MAFFT_VERSION
    try:
        proc = subprocess.run(
            [mafft_bin, "--version"], capture_output=True, text=True, timeout=10
        )
        raw = (proc.stdout or proc.stderr or "").strip()
        match = re.search(r"(?:v|version\s*)?(\d+\.\d+(?:\.\d+)?)", raw, re.I)
        if match:
            _MAFFT_VERSION = match.group(1)
    except Exception:
        return None
    return _MAFFT_VERSION


def _parse_fasta(text: str, *, allow_gaps: bool) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    seen: set[str] = set()
    current_id: str | None = None
    current: list[str] = []

    def flush() -> None:
        nonlocal current_id, current
        if current_id is None:
            return
        seq = "".join(current).replace(" ", "").upper()
        if not seq:
            raise ValueError(f"FASTA record {current_id!r} is empty")
        if not allow_gaps and "-" in seq:
            raise ValueError(f"Unaligned FASTA record {current_id!r} contains a gap")
        records.append((current_id, seq))
        current_id = None
        current = []

    for line_no, raw in enumerate((text or "").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            flush()
            header = line[1:].strip()
            if not header:
                raise ValueError(f"FASTA header at line {line_no} has no identifier")
            current_id = header.split()[0]
            if current_id in seen:
                raise ValueError(f"Duplicate FASTA identifier: {current_id}")
            seen.add(current_id)
        else:
            if current_id is None:
                raise ValueError(f"FASTA sequence appears before a header at line {line_no}")
            current.append("".join(line.split()))
    flush()
    if not records:
        raise ValueError("No FASTA records found")
    return records


def _validate_alignment(input_fasta: str, aligned_fasta: str) -> None:
    source = _parse_fasta(input_fasta, allow_gaps=False)
    aligned = _parse_fasta(aligned_fasta, allow_gaps=True)
    source_map = dict(source)
    aligned_map = dict(aligned)

    if set(source_map) != set(aligned_map) or len(source) != len(aligned):
        missing = sorted(set(source_map) - set(aligned_map))
        extra = sorted(set(aligned_map) - set(source_map))
        raise ValueError(f"MAFFT changed the record set (missing={missing}, extra={extra})")

    lengths = {len(seq) for seq in aligned_map.values()}
    if len(lengths) != 1:
        raise ValueError("MAFFT returned aligned rows of unequal length")

    for sid, original in source_map.items():
        if aligned_map[sid].replace("-", "").upper() != original.upper():
            raise ValueError(f"MAFFT output did not preserve residues for {sid!r}")


def run_local_mafft(
    fasta: str,
    strategy: str = "auto",
    threads: int = 1,
    timeout: int = 300,
) -> dict | None:
    """Run local MAFFT and return a validated alignment, or ``None`` on failure."""
    try:
        _parse_fasta(fasta, allow_gaps=False)
    except ValueError as exc:
        logger.warning("MAFFT input rejected: %s", exc)
        return None

    mafft_bin = _ensure_mafft()
    if not mafft_bin:
        logger.info("Local MAFFT not available")
        return None

    normalized_strategy = (strategy or "auto").lower().strip()
    flags = STRATEGY_FLAGS.get(normalized_strategy)
    if flags is None:
        logger.warning("Unknown MAFFT strategy %r", strategy)
        return None
    if int(threads) == 0:
        logger.warning("MAFFT threads cannot be zero")
        return None
    if int(timeout) <= 0:
        logger.warning("MAFFT timeout must be positive")
        return None

    with tempfile.NamedTemporaryFile(suffix=".fasta", mode="w", delete=False) as inf:
        inf.write(fasta)
        in_path = inf.name

    try:
        cmd = [mafft_bin, *flags, "--thread", str(int(threads)), in_path]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=int(timeout)
        )
        if result.returncode != 0:
            logger.warning("MAFFT failed (code %d): %s", result.returncode, result.stderr[:500])
            return None

        alignment = result.stdout
        if not alignment.strip():
            logger.warning("MAFFT returned an empty alignment")
            return None
        try:
            _validate_alignment(fasta, alignment)
        except ValueError as exc:
            logger.warning("MAFFT output rejected by integrity checks: %s", exc)
            return None

        return {
            "aln_fasta": alignment,
            "method": "mafft-local",
            "strategy": normalized_strategy,
            "threads": int(threads),
            "tool_version": _mafft_version(mafft_bin),
        }
    except subprocess.TimeoutExpired:
        logger.warning("Local MAFFT timed out after %ds", timeout)
        return None
    except FileNotFoundError:
        logger.warning("MAFFT binary not found at %s", mafft_bin)
        return None
    finally:
        try:
            os.unlink(in_path)
        except OSError:
            pass
