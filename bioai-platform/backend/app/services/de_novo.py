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

import httpx

logger = logging.getLogger(__name__)

IPRSCAN5_BASE = "https://www.ebi.ac.uk/Tools/services/rest/iprscan5"

POLL_INTERVAL_S = 3
MAX_POLLS = 60  # ~3 min worst case


def _clean_sequence(sequence: str) -> str:
    return "".join(c for c in (sequence or "") if c.isalpha()).upper()


# ── Domains/motifs without UniProt: InterProScan5 on the raw sequence ───────


async def interpro_sequence_search(sequence: str, email: str = "") -> dict:
    """Run InterProScan5 (EBI REST) against a raw sequence.

    Returns the same ``domains`` shape as
    ``domain_analysis.fetch_interpro_domains`` so downstream rendering is
    unchanged: ``{"domains": [{accession, name, source_db, start, end,
    score}], "sequence_length", "source": "interproscan5"}``.
    """
    seq = _clean_sequence(sequence)
    if len(seq) < 10:
        raise ValueError("Sequence too short for InterProScan (min 10 residues)")
    if len(seq) > 5000:
        raise ValueError("Sequence too long for InterProScan de novo scan (max 5000 residues)")

    from app.services.ssrf import validate_url

    validate_url(f"{IPRSCAN5_BASE}/run")

    async with httpx.AsyncClient(timeout=30) as client:
        submit_resp = await client.post(
            f"{IPRSCAN5_BASE}/run",
            data={
                "email": email or "bioflow@example.com",
                "stype": "protein",
                "sequence": seq,
            },
            headers={"Accept": "text/plain"},
        )
        if submit_resp.status_code != 200:
            detail = submit_resp.text[:200] if submit_resp.text else "no response body"
            raise ValueError(f"InterProScan submission failed (HTTP {submit_resp.status_code}): {detail}")
        job_id = submit_resp.text.strip()

        for _ in range(MAX_POLLS):
            await asyncio.sleep(POLL_INTERVAL_S)
            status_resp = await client.get(f"{IPRSCAN5_BASE}/status/{job_id}")
            status = status_resp.text.strip()
            if status == "FINISHED":
                break
            if status in ("ERROR", "FAILURE", "NOT_FOUND"):
                raise ValueError(f"InterProScan job failed: {status}")
        else:
            raise ValueError("InterProScan job timed out")

        result_resp = await client.get(
            f"{IPRSCAN5_BASE}/result/{job_id}/json", headers={"Accept": "application/json"}
        )
        result_resp.raise_for_status()
        data = result_resp.json()

    domains: list[dict] = []
    seq_len = len(seq)
    results = data.get("results") if isinstance(data, dict) else data
    for block in results or []:
        seq_len = block.get("length", seq_len)
        for match in block.get("matches", []) or []:
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
        "source": "interproscan5",
        "_note": "Sequence-search mode — no UniProt accession required",
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
    if not (10 <= len(seq) <= 768):
        raise ValueError(f"ESMFold requires 10–768 residues (got {len(seq)})")

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
