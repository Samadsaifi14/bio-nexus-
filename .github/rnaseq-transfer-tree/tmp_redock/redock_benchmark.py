"""Compatibility entry point for the canonical 1STP-BTN evidence runner."""
from pathlib import Path
import importlib.util
import os
import shutil
import sys

REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "benchmark/fixtures/docking/run_redock_panel.py"

def main():
    spec = importlib.util.spec_from_file_location("redock_runner", RUNNER)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    outdir = REPO / "benchmark/results/docking/canonical"
    sys.argv = [str(RUNNER), "--canonical", "--outdir", str(outdir), *sys.argv[1:]]
    status = runner.main()
    if os.environ.get("BIONEXUS_REDOCK_REPORT"):
        shutil.copyfile(outdir / "latest.json", os.environ["BIONEXUS_REDOCK_REPORT"])
    return status

if __name__ == "__main__":
    raise SystemExit(main())
