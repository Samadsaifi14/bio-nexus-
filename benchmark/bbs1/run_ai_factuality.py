"""Score a frozen corpus of BioNexus AI explanations against deterministic results.

Input is JSONL. Each line must contain: case_id, tool, deterministic_result, explanation.
The runner reports numeric-claim fidelity, structured-identifier fidelity and unsupported
structured-claim rate. It does not assess whether unrestricted biological prose is true.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.benchmarking.ai_factuality import score_explanation


def main(corpus: Path, output: Path) -> int:
    cases = []
    with corpus.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            if not raw.strip(): continue
            record = json.loads(raw)
            for key in ("case_id", "tool", "deterministic_result", "explanation"):
                if key not in record: raise ValueError(f"line {line_no}: missing {key}")
            score = score_explanation(record["explanation"], record["deterministic_result"])
            cases.append({"case_id": record["case_id"], "tool": record["tool"], **score.to_dict()})
    if not cases: raise ValueError("Corpus contains no cases")
    total_num = sum(c["numeric_claim_count"] for c in cases)
    supported_num = sum(c["supported_numeric_claim_count"] for c in cases)
    total_ids = sum(c["identifier_claim_count"] for c in cases)
    supported_ids = sum(c["supported_identifier_claim_count"] for c in cases)
    total_structured = total_num + total_ids
    unsupported = (total_num - supported_num) + (total_ids - supported_ids)
    result = {
        "suite": "BBS-1 AI factual grounding",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_count": len(cases),
        "numeric_claim_fidelity": 1.0 if total_num == 0 else supported_num / total_num,
        "identifier_claim_fidelity": 1.0 if total_ids == 0 else supported_ids / total_ids,
        "unsupported_structured_claim_rate": 0.0 if total_structured == 0 else unsupported / total_structured,
        "all_cases_structurally_grounded": all(c["passed"] for c in cases),
        "cases": cases,
        "claim_boundary": "Metrics cover numeric values and structured identifiers only. Free-form mechanistic or causal biological statements require separate expert/source review.",
    }
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_cases_structurally_grounded"] else 1

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("corpus", type=Path)
    p.add_argument("--output", type=Path, default=Path("results/ai_factuality.json"))
    a = p.parse_args(); raise SystemExit(main(a.corpus, a.output))
