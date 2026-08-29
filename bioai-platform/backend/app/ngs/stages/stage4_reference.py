"""
Stage 4 — Reference validation (blueprint Stage 4 / point 8).

The platform maintains a versioned reference registry instead of trusting a bare genome path.
This stage:
  * resolves the requested reference id against the registry
  * notes which artifacts the reference needs (FASTA, .fai, .dict, BWA index, GATK bundle,
    VEP cache, gnomAD, ClinVar) and whether they're present
  * CRITICALLY: validates build compatibility — refusing a stripped-provenance error such as a
    GRCh38 BAM paired with a GRCh37 annotation, which would silently produce wrong coordinates.

A BuildMismatch -> STOP (this is a fundamental provenance error).
"""

from __future__ import annotations

from typing import Any, Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule
from app.ngs.reference import (
    get_reference,
    validate_build_compatibility,
    describe,
    GenomeBuild,
)


def _resolve(ref_id: str) -> dict:
    try:
        ref = get_reference(ref_id)
        desc = describe(ref_id)
        desc["bundled"] = ref.bundled
        return desc
    except KeyError:
        return {"id": ref_id, "error": f"unknown reference '{ref_id}'"}


def _stage4_run(sample: dict, state: dict) -> tuple[dict, dict]:
    ref_id = sample.get("reference") or sample.get("reference_id")
    meta = sample.get("metadata") or {}
    annotation_build = sample.get("annotation_build") or meta.get("annotation_build")

    if not ref_id:
        return {"error": "no reference specified"}, {"reference_resolved": 0.0,
                                                     "build_compatible": 100.0}

    ref = _resolve(str(ref_id))
    alignment_build = ref.get("build")
    ref["requested"] = str(ref_id)

    compatible = True
    compat_msg = "reference declared; no annotation build to compare"
    if annotation_build and alignment_build:
        compatible, compat_msg = validate_build_compatibility(alignment_build, annotation_build)

    ref["build_compatible"] = compatible
    ref["build_message"] = compat_msg
    state.setdefault("reference", {})["declared"] = ref

    return ref, {
        "reference_resolved": 100.0 if "error" not in ref else 0.0,
        "build_compatible": 100.0 if compatible else 0.0,
    }


def stage4_contract() -> StageContract:
    return StageContract(
        step="reference_validation",
        tool="platform-reference-registry",
        version="0.1.0",
        inputs=["requested_reference", "annotation_build"],
        outputs=["reference_provenance"],
        rules=[
            ThresholdRule(name="reference_resolved", metric="reference_resolved",
                          evaluate=lambda v: QcStatus.PASS if v >= 100.0 else QcStatus.FAIL),
            ThresholdRule(name="build_compatible", metric="build_compatible",
                          evaluate=lambda v: QcStatus.PASS if v >= 100.0 else QcStatus.FAIL),
        ],
        fail_blocks=True,   # provenance errors must block
        run=_stage4_run,
    )


def run_reference_validation(sample: dict) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    contract = stage4_contract()
    data, metrics = _stage4_run(sample, {})
    result = QcResult.from_metrics(apply_rules(contract.resolve_rules(sample), metrics),
                                   fail_blocks=True)
    return {
        "result": {"step": "reference_validation", "qc": result.to_dict(),
                   "decision": result.decision.value, "data": data},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "reference": data},
    }
