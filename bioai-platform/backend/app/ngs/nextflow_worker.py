"""Detached local Nextflow process wrapper that leaves a durable status file."""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _write(path: Path, state: str, exit_code: int | None = None, message: str | None = None) -> None:
    event = {"state": state, "exit_code": exit_code, "message": message, "updated_at": datetime.now(timezone.utc).isoformat()}
    with path.with_name("worker_history.jsonl").open("a", encoding="utf-8") as history:
        history.write(json.dumps(event) + "\n")
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(event), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    if len(sys.argv) < 4:
        return 2
    status_path, log_path, command = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
    argv_bytes = json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode()
    status_path.with_name("worker_command.json").write_text(json.dumps({
        "command_argv": command, "command_sha256": hashlib.sha256(argv_bytes).hexdigest(),
        "evidence_class": "worker_execution", "sequencing_execution_verified": False,
    }, indent=2), encoding="utf-8")
    _write(status_path, "RUNNING")
    try:
        with log_path.open("w", encoding="utf-8") as log:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, text=True, check=False)
        state = "SUCCEEDED" if completed.returncode == 0 else "FAILED"
        digest = hashlib.sha256()
        with log_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        status_path.with_name("worker_log_sha256.txt").write_text(digest.hexdigest() + "\n", encoding="utf-8")
        _write(status_path, state, completed.returncode, None if completed.returncode == 0 else "Nextflow exited non-zero; inspect nextflow.log")
        return completed.returncode
    except Exception as exc:
        _write(status_path, "FAILED", None, f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
