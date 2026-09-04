"""Deterministic grounding metrics for BioNexus AI explanations.

The scorer intentionally does not decide whether free-form biological interpretation is true.
It verifies the subset of claims that can be checked mechanically against the deterministic
result: numeric tokens and structured biological identifiers.  This supports BBS-1 metrics
without promoting the LLM itself to scientific ground truth.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from typing import Any

_NUMERIC = re.compile(r"(?<![A-Za-z0-9_.])-?\d+(?:\.\d+)?(?:e[+-]?\d+)?%?", re.I)
# Common structured identifiers used in BioNexus outputs. Deliberately conservative.
_IDENTIFIER = re.compile(
    r"\b(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}|"
    r"GO:\d{7}|IPR\d{6}|PF\d{5}|[0-9][A-Za-z0-9]{3})\b",
    re.I,
)


def _normalise_number(token: str) -> str:
    value = token.rstrip("%").lower()
    try:
        number = float(value)
    except ValueError:
        return value
    # 1, 1.0 and 1.000 should be equivalent claims.
    return f"{number:.12g}"


def extract_numeric_tokens(text: str) -> list[str]:
    return [_normalise_number(x) for x in _NUMERIC.findall(text or "")]


def extract_identifiers(text: str) -> list[str]:
    return [x.upper() for x in _IDENTIFIER.findall(text or "")]


def flatten_result(result: Any) -> str:
    return json.dumps(result, sort_keys=True, ensure_ascii=False, default=str)


@dataclass(frozen=True)
class FactualityScore:
    numeric_claim_count: int
    supported_numeric_claim_count: int
    unsupported_numeric_claims: list[str]
    numeric_claim_fidelity: float
    identifier_claim_count: int
    supported_identifier_claim_count: int
    unsupported_identifiers: list[str]
    identifier_claim_fidelity: float
    unsupported_structured_claim_rate: float
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_explanation(explanation: str, deterministic_result: Any) -> FactualityScore:
    source = flatten_result(deterministic_result)
    source_numbers = set(extract_numeric_tokens(source))
    source_ids = set(extract_identifiers(source))
    generated_numbers = extract_numeric_tokens(explanation)
    generated_ids = extract_identifiers(explanation)

    unsupported_numbers = [x for x in generated_numbers if x not in source_numbers]
    unsupported_ids = [x for x in generated_ids if x not in source_ids]
    supported_num = len(generated_numbers) - len(unsupported_numbers)
    supported_id = len(generated_ids) - len(unsupported_ids)
    numeric_fidelity = 1.0 if not generated_numbers else supported_num / len(generated_numbers)
    id_fidelity = 1.0 if not generated_ids else supported_id / len(generated_ids)
    total = len(generated_numbers) + len(generated_ids)
    unsupported_rate = 0.0 if total == 0 else (len(unsupported_numbers) + len(unsupported_ids)) / total
    return FactualityScore(
        numeric_claim_count=len(generated_numbers),
        supported_numeric_claim_count=supported_num,
        unsupported_numeric_claims=unsupported_numbers,
        numeric_claim_fidelity=numeric_fidelity,
        identifier_claim_count=len(generated_ids),
        supported_identifier_claim_count=supported_id,
        unsupported_identifiers=unsupported_ids,
        identifier_claim_fidelity=id_fidelity,
        unsupported_structured_claim_rate=unsupported_rate,
        passed=(len(unsupported_numbers) == 0 and len(unsupported_ids) == 0),
    )
