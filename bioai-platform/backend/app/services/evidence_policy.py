"""Evidence classification and claim-admission policy for BioNexus.

The policy is deliberately conservative.  It classifies *how* a statement was
obtained, not whether it is biologically true, and rejects AI statements that
cannot be linked to recorded evidence.  Numeric claims receive an additional
exact-token fidelity check against the deterministic evidence payload.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any


class EvidenceClass(str, Enum):
    DETERMINISTIC = "deterministic computation"
    REFERENCE = "reference retrieval"
    INFERENCE = "evidence-backed inference"
    HEURISTIC = "heuristic"
    AI = "AI-generated interpretation"
    OBSERVATION = "experimental observation"
    BENCHMARK = "benchmark result"
    UNSUPPORTED = "unsupported/insufficient evidence"


REFERENCE_SECTIONS = {"uniprot", "domains", "pathway_enrichment", "alphafold", "pdb", "go", "kegg", "pfam"}
DETERMINISTIC_SECTIONS = {"blast", "msa", "phylo", "docking", "md", "ngs", "stats", "primers", "sequence"}


def numbers(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?%?", text or "")


def classify_source(section: str, payload: Any) -> EvidenceClass:
    if section in REFERENCE_SECTIONS:
        return EvidenceClass.REFERENCE
    if section in DETERMINISTIC_SECTIONS:
        return EvidenceClass.DETERMINISTIC
    if section.startswith("benchmark"):
        return EvidenceClass.BENCHMARK
    if section.startswith("observation") or section.startswith("experimental"):
        return EvidenceClass.OBSERVATION
    if section.startswith("heuristic"):
        return EvidenceClass.HEURISTIC
    return EvidenceClass.INFERENCE if payload else EvidenceClass.UNSUPPORTED


def evidence_text(context: dict, sections: list[str]) -> str:
    """Conservative flattened evidence text used by the numeric fidelity gate."""
    parts: list[str] = []
    for section in sections:
        value = context.get(section)
        if value is not None:
            parts.append(str(value))
    return " ".join(parts)


def classify_claim(*, sentence: str, evidence_sections: list[str], context: dict) -> dict:
    if not evidence_sections:
        return {
            "evidence_class": EvidenceClass.UNSUPPORTED.value,
            "admitted": False,
            "numeric_claims": numbers(sentence),
            "unsupported_numeric_claims": numbers(sentence),
            "reason": "no recorded evidence node supports this statement",
        }

    ev_numbers = set(numbers(evidence_text(context, evidence_sections)))
    claim_numbers = numbers(sentence)
    unsupported_numbers = [n for n in claim_numbers if n not in ev_numbers]
    if unsupported_numbers:
        return {
            "evidence_class": EvidenceClass.UNSUPPORTED.value,
            "admitted": False,
            "numeric_claims": claim_numbers,
            "unsupported_numeric_claims": unsupported_numbers,
            "reason": "numeric claim absent from supporting computation/reference payload",
        }

    classes = {classify_source(s, context.get(s)).value for s in evidence_sections}
    if EvidenceClass.DETERMINISTIC.value in classes and EvidenceClass.REFERENCE.value in classes:
        final_class = EvidenceClass.INFERENCE.value
    elif len(classes) == 1:
        final_class = next(iter(classes))
    else:
        final_class = EvidenceClass.INFERENCE.value
    return {
        "evidence_class": final_class,
        "admitted": True,
        "numeric_claims": claim_numbers,
        "unsupported_numeric_claims": [],
        "reason": "claim linked to recorded evidence",
    }
