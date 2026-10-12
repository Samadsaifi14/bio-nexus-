"""BioNexus Scientific Validation Registry.

Every scientific module carries one permanent machine-readable validation
state.  The application cannot promote a module manually: moving to a stronger
state (e.g. ``NOT_EVALUATED`` -> ``VALIDATED``) requires evidence produced by a
recorded independent benchmark run (retained artifacts + observed metrics).
"""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any

from .contract import canonical_json, sha256_hex


class ValidationState(str, Enum):
    NOT_EVALUATED = "NOT_EVALUATED"
    VALIDATION_PENDING = "VALIDATION_PENDING"
    SOURCE_CONCORDANCE_VALIDATED = "SOURCE_CONCORDANCE_VALIDATED"
    METHOD_VERIFIED = "METHOD_VERIFIED"
    VALIDATED = "VALIDATED"


_STATE_RANK = {
    ValidationState.NOT_EVALUATED: 0,
    ValidationState.VALIDATION_PENDING: 1,
    ValidationState.SOURCE_CONCORDANCE_VALIDATED: 2,
    ValidationState.METHOD_VERIFIED: 3,
    ValidationState.VALIDATED: 4,
}


_INITIAL_STATES: dict[str, ValidationState] = {
    "sequence_utilities": ValidationState.VALIDATED,
    "pairwise_alignment": ValidationState.VALIDATED,
    "consensus_sequencing": ValidationState.VALIDATION_PENDING,
    "blast": ValidationState.VALIDATION_PENDING,
    "msa": ValidationState.VALIDATION_PENDING,
    "phylo": ValidationState.VALIDATION_PENDING,
    "uniprot": ValidationState.SOURCE_CONCORDANCE_VALIDATED,
    "interpro": ValidationState.SOURCE_CONCORDANCE_VALIDATED,
    "pfam": ValidationState.SOURCE_CONCORDANCE_VALIDATED,
    "castp": ValidationState.NOT_EVALUATED,
    "fpocket": ValidationState.VALIDATION_PENDING,
    "docking": ValidationState.NOT_EVALUATED,
    "md": ValidationState.METHOD_VERIFIED,
    "ngs_wgs_accuracy": ValidationState.NOT_EVALUATED,
    "rnaseq": ValidationState.VALIDATION_PENDING,
    "rna_deseq2_accuracy": ValidationState.NOT_EVALUATED,
    "reactome": ValidationState.VALIDATION_PENDING,
    "string": ValidationState.VALIDATION_PENDING,
    "primer3": ValidationState.VALIDATION_PENDING,
    "admet": ValidationState.VALIDATION_PENDING,
    "swissmodel": ValidationState.VALIDATION_PENDING,
    "structure_comparison": ValidationState.VALIDATION_PENDING,
    "alphafold_esmfold": ValidationState.VALIDATION_PENDING,
}


class RegistryError(RuntimeError):
    """Raised when a registry transition is not permitted."""


def _initial() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for module, state in _INITIAL_STATES.items():
        rows[module] = {
            "module": module,
            "state": state.value,
            "evidence": None,
            "transition_reason": "initial",
        }
    return rows


_REGISTRY: dict[str, dict[str, Any]] | None = None


def _registry() -> dict[str, dict[str, Any]]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _initial()
    return _REGISTRY


def registry_state() -> dict[str, dict[str, Any]]:
    """Defensive copy of the full registry (immutable for readers)."""
    return deepcopy(_registry())


def module_validation_state(module: str) -> ValidationState:
    """Current validation state for a module. Unknown modules are NOT_EVALUATED."""
    row = _registry().get(module)
    if row is None:
        return ValidationState.NOT_EVALUATED
    return ValidationState(row["state"])


def transition(
    module: str,
    target: ValidationState | str,
    *,
    evidence: dict[str, Any] | None = None,
    reason: str = "",
) -> dict[str, Any]:
    """Move a module to ``target``.

    Downgrades and no-ops are allowed.  Any upgrade requires a retained
    benchmark artifact set (``run_id`` + ``artifacts`` + ``metrics``); a bare
    manual call can never promote a module, mirroring the rule that
    NOT_EVALUATED cannot become VALIDATED by hand.
    """
    current = module_validation_state(module)
    target = ValidationState(target) if isinstance(target, str) else target
    current_idx = _STATE_RANK[current]
    target_idx = _STATE_RANK[target]

    row = _registry().setdefault(
        module,
        {"module": module, "state": current.value, "evidence": None, "transition_reason": "initial"},
    )

    if target_idx > current_idx and target_idx >= 2:
        if not _evidence_is_retained_benchmark(evidence):
            raise RegistryError(
                f"Cannot promote '{module}' from {current.value} to {target.value}: "
                "state changes to a stronger claim require evidence from a retained "
                "independent benchmark run (run_id, artifacts and metrics)."
            )

    row["state"] = target.value
    row["evidence"] = deepcopy(evidence) if evidence else row["evidence"]
    row["transition_reason"] = reason or (
        "downgrade" if target_idx < current_idx else "no change"
    )
    return deepcopy(row)


def require_validation_evidence(
    *,
    run_id: str,
    artifacts: list[str],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Describe retained benchmark evidence used to justify a promotion."""
    return {
        "run_id": run_id,
        "artifacts": list(artifacts),
        "metrics": deepcopy(metrics),
        "evidence_sha256": sha256_hex(
            canonical_json({"run_id": run_id, "artifacts": artifacts, "metrics": metrics})
        ),
    }


def _evidence_is_retained_benchmark(evidence: dict[str, Any] | None) -> bool:
    if not evidence or not isinstance(evidence, dict):
        return False
    has_run_id = bool(evidence.get("run_id"))
    has_artifacts = bool(evidence.get("artifacts"))
    has_metrics = bool(evidence.get("metrics"))
    return has_run_id and has_artifacts and has_metrics