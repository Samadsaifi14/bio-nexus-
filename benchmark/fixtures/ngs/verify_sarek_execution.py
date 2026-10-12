#!/usr/bin/env python3
"""Inspect an exported owned run record and retained bundle; never launch compute."""
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "bioai-platform/backend"))
from app.ngs.execution_evidence import verify_execution_bundle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-record", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--report", type=Path, default=ROOT / "benchmark/results/ngs/sarek-execution/latest.json")
    args = parser.parse_args()
    if bool(args.run_record) != bool(args.bundle):
        parser.error("Provide both the owned run record and retained bundle")
    if args.run_record:
        report = verify_execution_bundle(json.loads(args.run_record.read_text()), args.bundle)
    else:
        report = {"status": "NOT_EXECUTED", "evidence_class": "execution_readiness",
                  "missing_local_tools": [name for name in ("nextflow", "java", "docker") if not shutil.which(name)],
                  "reason": "No actual Sarek run record and retained execution bundle supplied; a generated plan is not completed sequencing evidence",
                  "biological_validation": False}
    report["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"])
    return 0 if report["status"] == "RETAINED_EVIDENCE_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
