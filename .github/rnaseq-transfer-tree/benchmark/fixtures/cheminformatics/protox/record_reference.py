#!/usr/bin/env python3
"""Record a real ProTox 3.0 prediction for the pinned reference compounds.

This is the *only* sanctioned way to add CHEM-TOX ground truth: it calls the
live Charité service and writes a record with the model-version string and
exact parsed outputs. It never fabricates data.

Exit codes:
  0  recorded new reference snapshot successfully
  2  live service unavailable / quota / network error (NOT a data failure;
     the benchmark remains "not externally benchmarked", which is honest)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent
REPO = FIXTURE_DIR.parents[3]
sys.path.insert(0, str(REPO / "bioai-platform" / "backend"))

from app.tools.protox import ProToxError, predict_toxicity  # noqa: E402


COMPOUNDS = json.loads((FIXTURE_DIR / "protox_contract.json").read_text(encoding="utf-8"))["reference_compounds"]


async def record() -> list[dict]:
    records = []
    for compound in COMPOUNDS:
        result = await predict_toxicity(smiles=compound["smiles"], name=compound["name"])
        records.append({
            "compound": compound,
            "task_id": result["task_id"],
            "input_type": result["input_type"],
            "requested_models": result["requested_models"],
            "acute_toxicity": result["acute_toxicity"],
            "model_results": result["model_results"],
            "toxicity_targets": result["toxicity_targets"],
            "methodology": result["methodology"],
        })
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", type=Path, default=FIXTURE_DIR.parents[2] / "results" / "cheminformatics" / "protox")
    args = parser.parse_args()

    try:
        records = asyncio.run(record())
    except ProToxError as exc:
        print(f"PROTOX LIVE CAPTURE UNAVAILABLE: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # network/timeouts
        print(f"PROTOX LIVE CAPTURE FAILED: {exc}", file=sys.stderr)
        return 2

    args.outdir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "bionexus-protox-live-capture/v1",
        "captured": str(date.today()),
        "service": "ProTox 3.0 (Charité)",
        "records": records,
    }
    path = args.outdir / f"live_capture_{date.today().isoformat()}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="")
    print(f"PROTOX LIVE CAPTURE RECORDED: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())