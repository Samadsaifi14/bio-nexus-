"""Reproducibility Ledger (BioNexus 2.0, Component 16 / elevated capability E1).

The ledger is the experiment's provenance backbone: every engine/tool step
records a "carbon" — input reference, process (tool + parameters), and output
digest — chained by sha256 hashes in strict sequence. Enforcement verifies the
chain is linear, hash-consistent, and that every step recorded both an input
and an output, so a published experiment can be re-traced deterministically
(user data can never be silently dropped from the record).

The ledger for a job is persisted as a JSON file (base dir overridable via the
BIONEXUS_LEDGER_DIR env var; ephemeral on Space deployments, durable locally).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

LEDGER_DIR = os.environ.get("BIONEXUS_LEDGER_DIR")
if not LEDGER_DIR:
    LEDGER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ledgers")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _digest(obj: Any) -> str:
    return _sha256(json.dumps(obj if obj is not None else {}, sort_keys=True, default=str))


def _ledger_path(job_id: str) -> str:
    return os.path.join(LEDGER_DIR, f"{job_id}.json")


# --- Ledger operations -----------------------------------------------------

def begin_ledger(job_id: str) -> dict:
    """Create (or return) an empty ledger for a job."""
    ledger = get_ledger(job_id)
    if ledger is not None:
        return ledger
    ledger = {"job_id": job_id, "created_at": _iso_now(), "carbons": []}
    _save(job_id, ledger)
    return ledger


def record_carbon(job_id: str, step: str, input_ref: Any, process: dict, output: Any) -> dict:
    """Append one linearized carbon to the ledger: input digest -> process ->
    output digest, hash-chained to the previous carbon."""
    ledger = begin_ledger(job_id)
    carbons = ledger["carbons"]
    seq = len(carbons) + 1
    prev_hash = carbons[-1]["carbon_hash"] if carbons else None
    input_digest = _digest(input_ref)
    output_digest = _digest(output)
    carbon = {
        "seq": seq,
        "step": step,
        "input_recorded": input_ref is not None,
        "input_digest": input_digest,
        "input_ref": input_ref,
        "process": process,
        "process_recorded": bool(process),
        "output_recorded": output is not None,
        "output_digest": output_digest,
        "prev_hash": prev_hash,
        "carbon_hash": _sha256(f"{seq}|{step}|{input_digest}|{json.dumps(process, sort_keys=True, default=str)}|{output_digest}|{prev_hash}"),
        "recorded_at": _iso_now(),
    }
    ledger["carbons"].append(carbon)
    ledger["updated_at"] = _iso_now()
    _save(job_id, ledger)
    return carbon


def get_ledger(job_id: str) -> Optional[dict]:
    path = _ledger_path(job_id)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Ledger read failed for %s: %s", job_id, e)
        return None


def _save(job_id: str, ledger: dict) -> None:
    os.makedirs(LEDGER_DIR, exist_ok=True)
    with open(_ledger_path(job_id), "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)


# --- Enforcement ------------------------------------------------------------

def enforce(ledger: dict | None) -> dict:
    """Validate the ledger's reproducibility invariants. Never silently passes
    an empty chain, a broken hash link, or a step that dropped its input."""
    checks: list[dict] = []
    if not ledger or not isinstance(ledger, dict):
        return {"valid": False, "checks": [
            {"name": "ledger_exists", "passed": False, "detail": "no ledger"},
            {"name": "carbon_chain_present", "passed": False, "detail": "no carbons"},
            {"name": "hash_chain_valid", "passed": False, "detail": "nothing to verify"},
            {"name": "inputs_recorded", "passed": False, "detail": "nothing recorded"},
            {"name": "outputs_recorded", "passed": False, "detail": "nothing recorded"},
            {"name": "linear_sequence", "passed": False, "detail": "nothing recorded"},
        ]}

    carbons = ledger.get("carbons") or []
    chain_present = len(carbons) >= 1

    linear = chain_present
    hashes_ok = chain_present
    inputs_ok = chain_present
    outputs_ok = chain_present
    processes_ok = chain_present
    for i, c in enumerate(carbons):
        seq_expected = i + 1
        if c.get("seq") != seq_expected:
            linear = False
        if i and c.get("prev_hash") != carbons[i - 1].get("carbon_hash"):
            hashes_ok = False
        recomputed = _sha256(
            f"{c.get('seq')}|{c.get('step')}|{c.get('input_digest')}|"
            f"{json.dumps(c.get('process'), sort_keys=True, default=str)}|{c.get('output_digest')}|{c.get('prev_hash')}"
        )
        if recomputed != c.get("carbon_hash"):
            hashes_ok = False
        if not c.get("input_recorded", False):
            inputs_ok = False
        if not c.get("output_recorded", False):
            outputs_ok = False
        if not c.get("process_recorded", False):
            processes_ok = False
    if not chain_present:
        linear = hashes_ok = inputs_ok = outputs_ok = processes_ok = False

    checks = [
        {"name": "ledger_exists", "passed": True, "detail": ledger.get("job_id")},
        {"name": "carbon_chain_present", "passed": chain_present, "detail": f"{len(carbons)} carbons"},
        {"name": "hash_chain_valid", "passed": hashes_ok and chain_present, "detail": "linked sha256 chain"},
        {"name": "inputs_recorded", "passed": inputs_ok, "detail": "every carbon has an input digest"},
        {"name": "outputs_recorded", "passed": outputs_ok, "detail": "every carbon has an output digest"},
        {"name": "process_recorded", "passed": processes_ok, "detail": "every carbon names its process"},
        {"name": "linear_sequence", "passed": linear, "detail": "seq 1..N, strictly chained"},
    ]
    return {"valid": all(c["passed"] for c in checks), "checks": checks}