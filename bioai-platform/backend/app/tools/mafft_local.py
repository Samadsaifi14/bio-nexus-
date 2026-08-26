"""Local MAFFT multiple sequence alignment wrapper.

Calls the locally installed MAFFT binary for fast, offline MSA.
Falls back to the EBI remote MAFFT service or other EBI tools
when the local binary is unavailable.

MAFFT strategies:
- FFT-NS-2: fast, default for large datasets (up to ~30k sequences)
- L-INS-i: accurate, iterative refinement (best for <200 sequences)
- auto: automatic strategy selection based on dataset size
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

_MAFFT_BIN: str | None = None


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


def run_local_mafft(
    fasta: str,
    strategy: str = "auto",
    threads: int = 1,
    timeout: int = 300,
) -> dict | None:
    """Run local MAFFT on a FASTA-formatted string.

    Args:
        fasta: FASTA-formatted input sequences
        strategy: MAFFT strategy - "auto", "fft-ns-2", "l-ins-i", "g-ins-i", "e-ins-i"
        threads: number of threads (MAFFT supports multithreading)
        timeout: maximum seconds to wait

    Returns:
        {"aln_fasta": "...", "method": "mafft-local"} or None if MAFFT unavailable
    """
    mafft_bin = _ensure_mafft()
    if not mafft_bin:
        logger.info("Local MAFFT not available")
        return None

    # Map strategy names to MAFFT flags
    strategy_flags = {
        "auto": ["--auto"],
        "fft-ns-2": ["--fft", "--retree", "2"],
        "fft-ns-i": ["--fft", "--retree", "1", "--iterate"],
        "l-ins-i": ["--localpair", "--maxiterate", "1000"],
        "g-ins-i": ["--globalpair", "--maxiterate", "1000"],
        "e-ins-i": ["--epg", "--maxiterate", "1000"],
    }
    flags = strategy_flags.get(strategy, ["--auto"])

    with tempfile.NamedTemporaryFile(suffix=".fasta", mode="w", delete=False) as inf:
        inf.write(fasta)
        in_path = inf.name

    out_path = in_path + ".aln"
    try:
        cmd = [mafft_bin] + flags + ["--thread", str(threads), in_path]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.warning("MAFFT failed (code %d): %s", result.returncode, result.stderr[:500])
            return None

        if os.path.isfile(out_path):
            with open(out_path) as f:
                aln = f.read()
        else:
            aln = result.stdout

        if not aln.strip():
            return None

        return {
            "aln_fasta": aln,
            "method": "mafft-local",
        }
    except subprocess.TimeoutExpired:
        logger.warning("Local MAFFT timed out after %ds", timeout)
        return None
    except FileNotFoundError:
        logger.warning("MAFFT binary not found at %s", mafft_bin)
        return None
    finally:
        for p in (in_path, out_path):
            try:
                os.unlink(p)
            except OSError:
                pass
