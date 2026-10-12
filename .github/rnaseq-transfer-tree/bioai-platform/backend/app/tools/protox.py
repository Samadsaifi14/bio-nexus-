"""ProTox 3.0 (Charité) ML-based chemical toxicity prediction client.

Queries the documented public POST interface used by the official
`protox3_api.py` sample script:

  1. POST /protox3/src/api_enqueue.php
       data: input_type (name|smiles), input, requested_data (JSON list of model groups)
     -> returns a task id
  2. POST /protox3/src/api_retrieve.php  data: id=<task id>
     -> 200 with non-empty body when computation finished (404 while pending)
  3. GET  /protox3/csv/<task id>_{tox_class,result,tox_targets}.csv
     -> tab-separated prediction CSVs

The server rate-limits per source IP (250 queries/day) and queues requests,
so this module polls with backoff and enforces an overall deadline.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import time

import httpx

logger = logging.getLogger(__name__)

_ENQUEUE_URL = "https://tox.charite.de/protox3/src/api_enqueue.php"
_RETRIEVE_URL = "https://tox.charite.de/protox3/src/api_retrieve.php"
_CSV_BASE = "https://tox.charite.de/protox3/csv/"
_TIMEOUT = 20.0
_POLL_INTERVAL = 8.0
_MAX_WAIT = 300.0  # overall budget for a single prediction run (seconds)

# All computationally intensive model shorthands (from the official script).
ALL_MODELS = (
    "dili neuro nephro respi cardio carcino immuno mutagen cyto bbb eco clinical nutri "
    "nr_ahr nr_ar nr_ar_lbd nr_aromatase nr_er nr_er_lbd nr_ppar_gamma "
    "sr_are sr_hse sr_mmp sr_p53 sr_atad5 "
    "mie_thr_alpha mie_thr_beta mie_ttr mie_ryr mie_gabar mie_nmdar mie_ampar mie_kar "
    "mie_ache mie_car mie_pxr mie_nadhox mie_vgsc mie_nis "
    "CYP1A2 CYP2C19 CYP2C9 CYP2D6 CYP3A4 CYP2E1"
)

# Default model groups: acute toxicity + toxicity targets are always computed
# by the server; the rest are curated organ/endpoint models that add the most
# decision value without doubling compute time.
DEFAULT_MODELS = (
    "acute_tox tox_targets "
    "dili neuro nephro respi cardio carcino immuno mutagen cyto"
)


class ProToxError(Exception):
    """Raised when ProTox is unreachable or the query fails."""


def _normalize_header(name: str) -> str:
    return name.strip().strip('"').strip().lower().replace(" ", "_")


def _parse_tsv(text: str) -> list[dict]:
    """Parse a ProTox tab-separated CSV into a list of lowercase-keyed dicts."""
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    if not reader.fieldnames:
        return []
    return [{_normalize_header(k): (v or "").strip() for k, v in row.items() if k}
            for row in reader]


async def _enqueue(client: httpx.AsyncClient, input_type: str, input_value: str,
                   models: list[str]) -> str:
    """Submit a query and return the task id."""
    resp = await client.post(
        _ENQUEUE_URL,
        data={"input_type": input_type, "input": input_value,
              "requested_data": json.dumps(models)},
    )
    if resp.status_code == 403:
        raise ProToxError("ProTox daily quota exceeded (250 queries/IP/day). Try again tomorrow.")
    if resp.status_code == 429:
        raise ProToxError("ProTox is throttling requests. Try again in a few minutes.")
    if resp.status_code != 200:
        raise ProToxError(
            f"ProTox submit failed (HTTP {resp.status_code}). "
            "The ProTox server may be temporarily unavailable."
        )
    task_id = resp.text.strip().strip('"')
    if not task_id:
        raise ProToxError("ProTox returned an empty task id.")
    return task_id


async def _wait_for_result(client: httpx.AsyncClient, task_id: str) -> None:
    """Poll the retrieve endpoint until computation completes or deadline hits."""
    deadline = time.monotonic() + _MAX_WAIT
    while time.monotonic() < deadline:
        resp = await client.post(_RETRIEVE_URL, data={"id": task_id})
        if resp.status_code == 200 and resp.text.strip():
            return
        if resp.status_code == 403:
            raise ProToxError("ProTox daily quota exceeded (250 queries/IP/day).")
        if resp.status_code not in (200, 404):
            raise ProToxError(
                f"ProTox status check failed (HTTP {resp.status_code}). "
                "The ProTox server may be temporarily unavailable."
            )
        await asyncio.sleep(_POLL_INTERVAL)
    raise ProToxError("ProTox computation timed out. Try fewer models or retry later.")


async def _fetch_csv(client: httpx.AsyncClient, task_id: str, suffix: str) -> list[dict]:
    resp = await client.get(f"{_CSV_BASE}{task_id}_{suffix}.csv")
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return _parse_tsv(resp.text)


async def predict_toxicity(
    smiles: str | None = None,
    name: str | None = None,
    models: str | None = None,
) -> dict:
    """Run a ProTox 3.0 prediction and return structured results.

    Provide exactly one of ``smiles`` or ``name``. ``models`` is a
    space-separated list of model shorthands (see ALL_MODELS); defaults to
    DEFAULT_MODELS. Passing "ALL_MODELS" selects every available model.
    """
    if not smiles and not name:
        raise ProToxError("Provide a SMILES string or a compound name.")
    if smiles and name:
        raise ProToxError("Provide either a SMILES string or a compound name, not both.")

    input_type = "smiles" if smiles else "name"
    input_value = (smiles or name).strip()

    requested = (models or DEFAULT_MODELS).strip()
    if "ALL_MODELS" in requested.split():
        requested = " ".join(dict.fromkeys((requested.replace("ALL_MODELS", "").split() + ALL_MODELS.split())))
    model_groups = [requested]

    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        task_id = await _enqueue(client, input_type, input_value, model_groups)
        await _wait_for_result(client, task_id)
        acute = await _fetch_csv(client, task_id, "tox_class")
        models_csv = await _fetch_csv(client, task_id, "result")
        targets = await _fetch_csv(client, task_id, "tox_targets")

    acute_tox = {}
    for row in acute:
        for key, value in row.items():
            if value and key not in ("input", "type"):
                acute_tox[key] = value

    return {
        "task_id": task_id,
        "input": input_value,
        "input_type": input_type,
        "requested_models": requested,
        "acute_toxicity": acute_tox,
        "model_results": models_csv,
        "toxicity_targets": targets,
        "methodology": {
            "tier": "3a",
            "confidence": "model-based",
            "method": "ProTox 3.0 (Charité) — molecular similarity + Random Forest ML classifiers",
            "note": "Real ML toxicity prediction (61 endpoints). Academic/non-commercial use, for research screening not regulatory decisions.",
        },
    }
