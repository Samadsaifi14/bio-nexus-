"""Validate retained Sarek run artifacts; a launch plan cannot pass this gate."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_execution_bundle(record: dict, root: Path) -> dict:
    """Bind actual files to a run; completeness is not biological validation."""
    root = root.resolve()
    errors = []
    if record.get("state") != "SUCCEEDED" or record.get("exit_code") != 0:
        errors.append("Run has not completed successfully with an explicit zero exit state")

    def path_for(name: str) -> Path:
        path = root / name
        if not name or Path(name).is_absolute() or ".." in Path(name).parts or not path.resolve().is_relative_to(root) or path.is_symlink():
            raise ValueError("Evidence paths must remain inside the retained bundle")
        return path

    try:
        manifest_path = path_for("execution_evidence.json")
        manifest = json.loads(manifest_path.read_text())
        for field in ("run_id", "command_sha256", "workflow", "revision"):
            if not record.get(field) or manifest.get(field) != record[field]:
                errors.append("Run identity mismatch: " + field)
        if manifest.get("workflow") != "nf-core/sarek" or manifest.get("revision") != "3.10.0":
            errors.append("Expected pinned nf-core/sarek 3.10.0")
        if not manifest.get("nextflow_version"):
            errors.append("Nextflow version is missing")
        checksums = {}
        output_paths = []
        for category in ("inputs", "references", "outputs"):
            members = manifest.get(category)
            if not isinstance(members, list) or not members:
                errors.append(category + " checksum records are missing")
                continue
            for member in members:
                name, expected = member["path"], member["sha256"]
                actual = sha256(path_for(name))
                if not re.fullmatch(r"[0-9a-f]{64}", expected) or actual != expected:
                    errors.append("Checksum mismatch: " + name)
                checksums[name] = actual
                if category == "outputs":
                    output_paths.append(name)
        from app.ngs.production import REQUIRED_ARTIFACTS
        import fnmatch
        for group in REQUIRED_ARTIFACTS:
            for alternatives in group["patterns"]:
                if not any((pattern.endswith("/") and name.startswith(pattern)) or fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(name, pattern.removeprefix("**/"))
                           for name in output_paths for pattern in alternatives.split("|")):
                    errors.append("Required output missing: " + group["id"] + ": " + alternatives)
        trace_path = path_for(manifest["trace"])
        if manifest["trace"] not in checksums:
            errors.append("Execution trace is absent from the checksummed outputs")
        with trace_path.open() as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        if not rows or not {"name", "status", "exit", "container"}.issubset(rows[0]):
            errors.append("Trace needs executed processes, status, exit and immutable container identities")
        else:
            final_attempts = {}
            for row in rows:
                final_attempts[row["name"]] = row
                if not re.search(r"@sha256:[0-9a-f]{64}$", row["container"]):
                    errors.append("Container digest missing for process: " + row["name"])
            for name, row in final_attempts.items():
                if row["status"] not in {"COMPLETED", "CACHED"} or row["exit"] != "0":
                    errors.append("Final process attempt did not succeed: " + name)
        return {"status": "INSUFFICIENT_EVIDENCE" if errors else "RETAINED_EVIDENCE_VERIFIED",
                "evidence_class": "executed_workflow_artifact_contract", "errors": errors,
                "verified_file_sha256": checksums, "manifest_sha256": sha256(manifest_path),
                "process_attempts": len(rows), "biological_validation": False}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"status": "INSUFFICIENT_EVIDENCE", "errors": [*errors, str(exc)],
                "evidence_class": "executed_workflow_artifact_contract", "biological_validation": False}
