"""Machine-readable scientific validation registry.

There is deliberately no mutation API.  A module can reach VALIDATED only from
an integrity-checked benchmark evidence artifact committed under
``benchmarks/validation-registry``.  UI state, user input, and AI text cannot
promote scientific validation.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "benchmarks" / "validation-registry"

# Conservative software/method states.  None of these entries is allowed to
# declare VALIDATED; that state is derived only from benchmark evidence below.
_BASE_REGISTRY: dict[str, dict[str, Any]] = {
    "sequence_utilities": {"status": "METHOD_VERIFIED", "scope": "IUPAC-aware DNA/RNA/protein utilities; randomized Biopython concordance", "contract_migrated": False},
    "pairwise_alignment": {"status": "METHOD_VERIFIED", "scope": "global/local alignment coordinates and invariants", "contract_migrated": False},
    "admet_descriptors": {"status": "METHOD_VERIFIED", "scope": "deterministic RDKit descriptors and explicitly labelled rule-based alerts", "contract_migrated": False},
    "admet_predictive": {"status": "NOT_EVALUATED", "scope": "predictive ADMET endpoints require a validated model, applicability domain and uncertainty", "contract_migrated": False},
    "blast": {"status": "VALIDATION_PENDING", "scope": "NCBI/EBI parser and routing verification; permanent multi-sequence reference benchmark still required", "contract_migrated": False},
    "msa": {"status": "METHOD_VERIFIED", "scope": "engine input/output integrity and fallback provenance", "contract_migrated": False},
    "phylogeny": {"status": "METHOD_VERIFIED", "scope": "tree-input validation, model/provenance and deterministic invariants", "contract_migrated": False},
    "uniprot": {"status": "SOURCE_CONCORDANCE_VALIDATED", "scope": "retrieved UniProt source fields and provenance", "contract_migrated": False},
    "interpro_domains": {"status": "VALIDATION_PENDING", "scope": "source/version and member-signature parity", "contract_migrated": False},
    "castp": {"status": "NOT_EVALUATED", "scope": "CASTp-specific output requires CASTp source evidence", "contract_migrated": False},
    "fpocket": {"status": "VALIDATION_PENDING", "scope": "fpocket output/provenance and reference fixtures", "contract_migrated": False},
    "pocket_heuristic": {"status": "METHOD_VERIFIED", "scope": "exploratory geometric/SASA heuristic only; not CASTp or fpocket", "contract_migrated": False},
    "primer3": {"status": "VALIDATION_PENDING", "scope": "Primer3 parity plus genome-wide specificity benchmark", "contract_migrated": False},
    "reactome": {"status": "VALIDATION_PENDING", "scope": "source-release and complete enrichment-table parity", "contract_migrated": False},
    "string": {"status": "VALIDATION_PENDING", "scope": "STRING evidence-channel and network-version parity", "contract_migrated": False},
    "structure_analysis": {"status": "VALIDATION_PENDING", "scope": "wwPDB/AlphaFold quality-source parity", "contract_migrated": False},
    "structure_preparation": {"status": "VALIDATION_PENDING", "scope": "preparation ledger and artifact parity", "contract_migrated": False},
    "structure_comparison": {"status": "METHOD_VERIFIED", "scope": "Foldseek TMalign-mode output with qTM semantics", "contract_migrated": False},
    "structure_prediction": {"status": "VALIDATION_PENDING", "scope": "ESMFold prediction provenance/confidence; not experimental validation", "contract_migrated": False},
    "swissmodel": {"status": "VALIDATION_PENDING", "scope": "quality-field/source parity and downstream gating", "contract_migrated": False},
    "docking": {"status": "NOT_EVALUATED", "scope": "canonical redocking benchmark with predeclared RMSD acceptance threshold", "contract_migrated": False},
    "md": {"status": "METHOD_VERIFIED", "scope": "short implicit-solvent OpenMM workflow only", "contract_migrated": False},
    "ngs_wgs_accuracy": {"status": "NOT_EVALUATED", "scope": "BioNexus-produced Sarek callset versus matching GIAB truth/confident regions", "contract_migrated": False},
    "giab_evaluator": {"status": "METHOD_VERIFIED", "scope": "retained HG002 chr20 truth-evaluation harness; does not establish BioNexus caller accuracy", "contract_migrated": False},
    "rnaseq": {"status": "METHOD_VERIFIED", "scope": "retained real-data GSE67196 DESeq2 execution with locked public-source, table, plot-source and figure hashes; experimental unit remains undeclared and biological/clinical interpretation is outside this software verification", "contract_migrated": False},
    "motif_scanner": {"status": "VALIDATION_PENDING", "scope": "PROSITE-derived/custom/local motif classes must remain distinct", "contract_migrated": False},
    "function_evidence": {"status": "VALIDATION_PENDING", "scope": "claim-to-InterPro/member-signature/source traceability", "contract_migrated": False},
    "dotplot": {"status": "METHOD_VERIFIED", "scope": "calculated dots and downsampling disclosure; pattern interpretation remains heuristic", "contract_migrated": False},
    "scientific_result_contract": {"status": "VALIDATION_PENDING", "scope": "platform migration to authoritative ScientificResult responses", "contract_migrated": True},
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _load_promotion(module: str) -> dict[str, Any] | None:
    path = EVIDENCE_DIR / f"{module}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("module") != module or payload.get("status") != "VALIDATED" or payload.get("passed") is not True:
        return None
    evidence = payload.get("evidence")
    expected = payload.get("evidence_sha256")
    if not isinstance(evidence, dict) or not isinstance(expected, str):
        return None
    actual = hashlib.sha256(_canonical(evidence)).hexdigest()
    if actual != expected:
        return None
    required = ("benchmark_id", "run_identifier", "acceptance_criteria", "results")
    if any(not evidence.get(key) for key in required):
        return None
    return payload


def get_validation_registry() -> dict[str, Any]:
    registry = deepcopy(_BASE_REGISTRY)
    for module, record in registry.items():
        promotion = _load_promotion(module)
        if promotion:
            record["status"] = "VALIDATED"
            record["benchmark_evidence"] = promotion["evidence"]
            record["evidence_sha256"] = promotion["evidence_sha256"]
        else:
            record["benchmark_evidence"] = None
    return {
        "policy": {
            "manual_validation_promotion": False,
            "validated_requires_benchmark_artifact": True,
            "ai_may_change_validation_state": False,
            "missing_evidence_is_negative_finding": False,
        },
        "modules": registry,
    }
