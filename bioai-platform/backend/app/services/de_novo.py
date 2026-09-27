"""Tier-6 de novo characterization (techspec.md §1.2).

For sequences that fail every identifier-resolution tier: swap "look it up"
tools for "characterize from sequence alone" tools. Everything here accepts a
raw sequence and never needs a UniProt accession.

Every result carries explicit ``source`` / ``_note`` markers so the UI can
label it as predicted rather than implying database-grade certainty.
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

IPRSCAN6_BASE = "https://www.ebi.ac.uk/Tools/services/rest/iprscan6"

# InterProScan 6 is an asynchronous EBI job: submit, then poll until FINISHED.
# Measured latency for a single short protein is 7-20+ minutes, so the client
# must not block a caller for that long. ``interpro_sequence_search`` therefore
# submits, waits a bounded budget, and otherwise hands back a "still running"
# marker carrying the EBI job id for the background poller to finish.
POLL_INTERVAL_S = 3
INLINE_WAIT_BUDGET_S = int(os.getenv("IPRSCAN_INLINE_WAIT_S", "45"))
# Hard ceiling for the background poller before it gives up on a submission.
MAX_POLL_S = int(os.getenv("IPRSCAN_MAX_POLL_S", "3600"))
SUBMIT_TIMEOUT_S = 30
STATUS_TIMEOUT_S = 30


def _clean_sequence(sequence: str) -> str:
    return "".join(c for c in (sequence or "") if c.isalpha()).upper()


# ── Domains/motifs without UniProt: InterProScan 6 on the raw sequence ────────
#
# InterProScan 5 was retired by EBI (its REST endpoint now returns
# "Tool 'interproscan5' was not found"), so both the URL and the tool label move
# to iprscan6. The v6 JSON keeps the v5 results -> matches -> signature ->
# locations shape, so the parser below is unchanged.


async def submit_interpro_scan(sequence: str, email: str = "") -> str:
    """Submit a sequence to InterProScan 6 and return the EBI job id."""
    seq = _clean_sequence(sequence)
    if len(seq) < 10:
        raise ValueError("Sequence too short for InterProScan (min 10 residues)")
    if len(seq) > 5000:
        raise ValueError("Sequence too long for InterProScan de novo scan (max 5000 residues)")

    from app.services.ssrf import validate_url

    validate_url(f"{IPRSCAN6_BASE}/run")

    async with httpx.AsyncClient(timeout=SUBMIT_TIMEOUT_S) as client:
        resp = await client.post(
            f"{IPRSCAN6_BASE}/run",
            data={
                "email": email or "bioflow@example.com",
                "stype": "protein",
                "sequence": seq,
                "goterms": "true",
                "pathways": "true",
            },
            headers={"Accept": "text/plain"},
        )
    if resp.status_code != 200:
        detail = resp.text[:200] if resp.text else "no response body"
        raise ValueError(f"InterProScan submission failed (HTTP {resp.status_code}): {detail}")
    job_id = resp.text.strip()
    if not job_id:
        raise ValueError("InterProScan submission returned no job id")
    return job_id


async def poll_interpro_scan(job_id: str) -> str:
    """Return the EBI job status (``RUNNING`` / ``FINISHED`` / error token)."""
    from app.services.ssrf import validate_url

    validate_url(f"{IPRSCAN6_BASE}/status/{job_id}")
    async with httpx.AsyncClient(timeout=STATUS_TIMEOUT_S) as client:
        resp = await client.get(f"{IPRSCAN6_BASE}/status/{job_id}")
    return resp.text.strip()


async def fetch_interpro_result(job_id: str) -> dict:
    """Fetch and normalise a finished InterProScan 6 job."""
    from app.services.ssrf import validate_url

    validate_url(f"{IPRSCAN6_BASE}/result/{job_id}/json")
    async with httpx.AsyncClient(timeout=STATUS_TIMEOUT_S) as client:
        resp = await client.get(
            f"{IPRSCAN6_BASE}/result/{job_id}/json", headers={"Accept": "application/json"}
        )
        resp.raise_for_status()
        data = resp.json()
    return _normalize_interpro_json(data)


def _normalize_interpro_json(data) -> dict:
    """Map an InterProScan 6 JSON result to the shared ``domains`` shape.

    Unchanged from the v5 parser: v6 keeps ``results -> matches -> signature ->
    locations``. v6 omits some per-entry fields, so every access stays defensive.
    """
    domains: list[dict] = []
    results = data.get("results") if isinstance(data, dict) else data
    seq_len = 0
    for block in results or []:
        if isinstance(block, dict):
            seq_len = block.get("length", seq_len) or seq_len
        for match in (block.get("matches", []) if isinstance(block, dict) else None) or []:
            sig = match.get("signature", {}) or {}
            entry = sig.get("entry", {}) or {}
            lib = (sig.get("signatureLibraryRelease") or {}).get("library", "")
            name_raw = sig.get("name")
            if isinstance(name_raw, dict):
                name_str = name_raw.get("name", sig.get("accession", ""))
            else:
                name_str = name_raw or sig.get("accession", "")
            for loc in match.get("locations", []) or []:
                domains.append({
                    # Prefer the InterPro entry identity when present, else the
                    # member-database signature — same precedence as lookup mode.
                    "accession": entry.get("accession") or sig.get("accession", ""),
                    "name": entry.get("name") or name_str,
                    "source_db": (entry.get("sourceDatabase") or lib or "").upper(),
                    "start": int(loc.get("start", 0)),
                    "end": int(loc.get("end", 0)),
                    "score": loc.get("score"),
                    "_signature_accession": sig.get("accession", ""),
                })

    domains.sort(key=lambda d: d["start"])
    return {
        "domains": domains,
        "sequence_length": seq_len,
        "source": "interproscan6",
        "interpro_job_id": None,
        "_note": "Sequence-search mode — no UniProt accession required",
    }


async def interpro_sequence_search(sequence: str, email: str = "") -> dict:
    """Run InterProScan 6 (EBI REST) against a raw sequence.

    Returns the same ``domains`` shape as
    ``domain_analysis.fetch_interpro_domains`` so downstream rendering is
    unchanged: ``{"domains": [{accession, name, source_db, start, end,
    score}], "sequence_length", "source": "interproscan6"}``.

    Because the EBI job takes minutes, this waits only ``INLINE_WAIT_BUDGET_S``.
    If it has not finished it returns ``{"status": "running", "domains": [],
    "interpro_job_id": <id>}`` — an explicit "not yet" that the background poller
    completes; the caller must not present that as "no domains found".
    """
    seq = _clean_sequence(sequence)
    job_id = await submit_interpro_scan(sequence, email)

    deadline = asyncio.get_running_loop().time() + INLINE_WAIT_BUDGET_S
    while asyncio.get_running_loop().time() < deadline:
        status = await poll_interpro_scan(job_id)
        if status == "FINISHED":
            result = await fetch_interpro_result(job_id)
            result["interpro_job_id"] = job_id
            result["status"] = "complete"
            return result
        if status in ("ERROR", "FAILURE", "NOT_FOUND"):
            raise ValueError(f"InterProScan job failed: {status}")
        await asyncio.sleep(POLL_INTERVAL_S)

    # Still running upstream: hand back the id so it can be polled to completion
    # in the background rather than blocking this pipeline for 20 minutes.
    return {
        "domains": [],
        "sequence_length": len(seq),
        "source": "interproscan6",
        "status": "running",
        "interpro_job_id": job_id,
        "_note": "InterProScan 6 job submitted and still running; domains will appear when it finishes",
    }


async def await_interpro_result(job_id: str) -> dict:
    """Poll a submitted InterProScan 6 job to completion and return its result.

    Meant to be driven by a background task, never awaited inline by a request.
    On a terminal upstream failure it returns an ``error`` payload rather than
    raising, so a failed scan is recorded and shown instead of vanishing.
    """
    deadline = asyncio.get_running_loop().time() + MAX_POLL_S
    while asyncio.get_running_loop().time() < deadline:
        try:
            status = await poll_interpro_scan(job_id)
        except Exception as exc:
            logger.warning("InterProScan status check failed for %s: %s", job_id, exc)
            await asyncio.sleep(POLL_INTERVAL_S * 4)
            continue

        if status == "FINISHED":
            try:
                result = await fetch_interpro_result(job_id)
            except Exception as exc:
                return {
                    "domains": [],
                    "sequence_length": 0,
                    "source": "interproscan6",
                    "status": "failed",
                    "interpro_job_id": job_id,
                    "error": f"InterProScan result could not be retrieved: {exc}",
                }
            result["interpro_job_id"] = job_id
            result["status"] = "complete"
            return result

        if status in ("ERROR", "FAILURE", "NOT_FOUND"):
            return {
                "domains": [],
                "sequence_length": 0,
                "source": "interproscan6",
                "status": "failed",
                "interpro_job_id": job_id,
                "error": f"InterProScan job failed upstream: {status}",
            }

        await asyncio.sleep(POLL_INTERVAL_S * 4)

    return {
        "domains": [],
        "sequence_length": 0,
        "source": "interproscan6",
        "status": "failed",
        "interpro_job_id": job_id,
        "error": f"InterProScan job did not finish within {MAX_POLL_S // 60} minutes",
    }


# ── Structure without AlphaFold DB: ESMFold ab initio ────────────────────────


def _mean_plddt_from_pdb(pdb_text: str) -> float | None:
    """ESMFold stores per-residue pLDDT in the B-factor column of CA atoms."""
    vals: list[float] = []
    for line in pdb_text.splitlines():
        if line.startswith(("ATOM", "HETATM")) and line[12:16].strip() == "CA":
            try:
                vals.append(float(line[60:66]))
            except ValueError:
                continue
    return round(sum(vals) / len(vals), 1) if vals else None


async def esmfold_structure(sequence: str) -> dict:
    """Predict an ab initio structure via ESMFold, shaped like an AlphaFold card.

    Same keys as ``AlphaFoldTool.run`` plus inline ``pdb_text`` and
    ``source="esmfold"`` so the viewer can render without a remote URL.
    """
    seq = _clean_sequence(sequence)
    if not (10 <= len(seq) <= 400):
        raise ValueError(f"ESMFold requires 10–400 residues (got {len(seq)})")

    from app.tools.structure_prep import esmfold_predict

    pdb_text = await esmfold_predict(seq)
    if not pdb_text:
        return {
            "structure_available": False,
            "source": "esmfold",
            "pdb_url": None,
            "cif_url": None,
            "confidence": None,
            "_note": "ESMFold could not predict a structure for this sequence",
        }

    mean_plddt = _mean_plddt_from_pdb(pdb_text)
    return {
        "structure_available": True,
        "source": "esmfold",
        "pdb_text": pdb_text,
        "pdb_url": None,
        "cif_url": None,
        "confidence": round(min(mean_plddt / 100, 0.99), 2) if mean_plddt else None,
        "mean_plddt": mean_plddt,
        "uniprot_accession": None,
        "_note": "Ab initio prediction (ESMFold) — no database match",
    }


# ── Composition stats (already accession-free; run unconditionally) ─────────


def composition_stats(sequence: str) -> dict:
    """Basic composition/stats via the existing sequence utilities."""
    seq = _clean_sequence(sequence)
    if not seq:
        raise ValueError("Empty sequence")

    from app.tools.sequence_utilities import analyze_sequence

    report = analyze_sequence(seq, seq_type="protein")
    report["source"] = "local"
    report["_note"] = "Computed directly from the submitted sequence"
    return report


# ── Function hints (composition-level heuristics, explicitly unscored) ──────


def function_hints(sequence: str) -> dict:
    """Composition-level functional hints.

    Heuristic only — there is no homolog to score against, so these are NOT
    database-grade GO terms. Labeled accordingly.
    """
    from app.tools.function_predict import _predict_from_sequence

    hint = _predict_from_sequence(_clean_sequence(sequence), pdb_id="de_novo")
    hint["source"] = "composition_heuristic"
    hint["_note"] = (
        "Heuristic composition-level hints — no identified homolog, "
        "not scored against any database"
    )
    return hint
