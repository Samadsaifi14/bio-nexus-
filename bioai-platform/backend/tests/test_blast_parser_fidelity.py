"""BLAST parser-fidelity benchmark gate (SEQ-BLAST extension).

Runs the offline runner over the committed reference bundle (currently the
synthetic structural fixture; a live NCBI capture swaps in when NCBI queues
are reachable) and asserts the parser preserves the field contract to
1000/1000 under the documented tolerance rules with download parity.

The origin label is asserted so a synthetic-structural bundle can never be
recorded as an NCBI-validated run.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BUNDLE = REPO / "benchmark" / "fixtures" / "sequence" / "blast_parser"
RUNNER = BUNDLE / "run_blast_parser_fidelity.py"
RESULTS = REPO / "benchmark" / "results" / "sequence" / "blast_parser"


def _run():
    return subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=str(REPO / "bioai-platform" / "backend"),
        capture_output=True, text=True, timeout=300,
    )


def test_blast_parser_fidelity_passes():
    proc = _run()
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]
    assert "PASS" in proc.stdout


def test_blast_parser_fidelity_record_persisted_and_honest():
    latest = json.loads((RESULTS / "latest.json").read_text(encoding="utf-8"))
    assert latest["status"] == "passed"
    assert latest["field_permille_exact_match"] == 1000
    assert latest["download_parity"]["roundtrip_ok"] is True
    assert latest["origin"] == "synthetic-structural", (
        "a live NCBI capture must be recorded with origin=ncbi-live"
    )