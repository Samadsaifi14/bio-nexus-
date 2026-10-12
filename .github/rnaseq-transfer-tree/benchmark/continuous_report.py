"""Create a machine-readable continuous-benchmark run report.

Designed for CI use. It records execution environment and benchmark test status
without converting test execution into claims of external scientific validation.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return os.getenv("GITHUB_SHA")


def _python_version() -> str:
    return platform.python_version()


def build_report() -> dict:
    return {
        "schema": "bionexus-continuous-benchmark-report/v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "github_run_id": os.getenv("GITHUB_RUN_ID"),
        "github_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        "runner": {
            "os": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "python": _python_version(),
        },
        "environment": {
            "runner_os": os.getenv("RUNNER_OS"),
            "python_executable": sys.executable,
        },
        "status_semantics": "CI success demonstrates regression compatibility for the executed fixtures; it does not by itself establish external biological validation.",
    }


def main() -> None:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "continuous-benchmark-report.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_report(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
