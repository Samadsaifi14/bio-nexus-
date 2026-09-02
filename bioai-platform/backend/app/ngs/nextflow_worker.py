"""Detached local Nextflow process wrapper that leaves a durable status file."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _write(path: Path, state: str, exit_code: int | None = None, message: str | None = None) -> None:
    path.write_text(json.dumps({"state": state, "exit_code": exit_code, "message": message, "updated_at": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")


def main() -> int:
    if len(sys.argv) < 4:
        return 2
    status_path, log_path, command = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
    _write(status_path, "RUNNING")
    try:
        with log_path.open("w", encoding="utf-8") as log:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, text=True, check=False)
        state = "SUCCEEDED" if completed.returncode == 0 else "FAILED"
        _write(status_path, state, completed.returncode, None if completed.returncode == 0 else "Nextflow exited non-zero; inspect nextflow.log")
        return completed.returncode
    except Exception as exc:
        _write(status_path, "FAILED", None, f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
