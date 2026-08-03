"""
Shared EBI MSA REST client, parameterized by tool base URL.

Verified live (2026-08-03) for clustalo / muscle / kalign / mafft / tcoffee:
all five expose the identical contract — POST ``{base}/run`` with
``email``/``stype``/``sequence``, poll ``{base}/status/{job}`` until FINISHED,
then fetch ``result/{job}/fa`` (FASTA alignment) and ``result/{job}/phylotree``
(Newick). The base URL is passed in full (per tool), never as a query param.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

EBI_TOOLS: dict[str, str] = {
    "clustalo": "https://www.ebi.ac.uk/Tools/services/rest/clustalo",
    "muscle": "https://www.ebi.ac.uk/Tools/services/rest/muscle",
    "kalign": "https://www.ebi.ac.uk/Tools/services/rest/kalign",
    "mafft": "https://www.ebi.ac.uk/Tools/services/rest/mafft",
    "tcoffee": "https://www.ebi.ac.uk/Tools/services/rest/tcoffee",
}

POLL_INTERVAL = 2
MAX_POLLS = 120
TREE_TYPES = ["phylotree"]


async def run_ebi_msa(
    base_url: str,
    sequence: str,
    stype: str = "protein",
    email: str = "bioflow@example.com",
) -> dict:
    """Submit ``sequence`` (FASTA) to an EBI MSA tool and wait for the alignment.

    Raises ValueError with a human-readable message on any failure.
    Returns ``{"job_id", "aln_fasta", "phylotree", "method"}``.
    """
    method = base_url.rstrip("/").rsplit("/", 1)[-1]

    async with httpx.AsyncClient(timeout=30) as client:
        submit_resp = await client.post(
            f"{base_url}/run",
            data={"email": email, "stype": stype, "sequence": sequence},
            headers={"Accept": "text/plain"},
        )
        if submit_resp.status_code != 200:
            detail = submit_resp.text[:200] if submit_resp.text else "no response body"
            raise ValueError(f"EBI submission failed (HTTP {submit_resp.status_code}): {detail}")
        job_id = submit_resp.text.strip()
        logger.info("EBI MSA job submitted (%s): %s", method, job_id)

        for _ in range(MAX_POLLS):
            await asyncio.sleep(POLL_INTERVAL)
            try:
                status_resp = await client.get(f"{base_url}/status/{job_id}")
                status = status_resp.text.strip()
            except Exception as e:
                logger.warning("EBI status poll failed: %s", e)
                continue
            logger.info("EBI MSA status (%s/%s): %s", method, job_id, status)
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise ValueError(f"EBI {method} job failed")
        else:
            raise ValueError(f"EBI {method} alignment timed out")

        await asyncio.sleep(1)

        fa_resp = await client.get(
            f"{base_url}/result/{job_id}/fa", headers={"Accept": "text/plain"}
        )
        if fa_resp.status_code != 200 or not fa_resp.text.strip():
            raise ValueError("Failed to fetch alignment result from EBI")
        aln_fasta = fa_resp.text

        phylotree = ""
        for t in TREE_TYPES:
            tr = await client.get(
                f"{base_url}/result/{job_id}/{t}", headers={"Accept": "text/plain"}
            )
            if tr.status_code == 200 and tr.text.strip():
                phylotree = tr.text
                break

    return {
        "job_id": job_id,
        "aln_fasta": aln_fasta,
        "phylotree": phylotree,
        "method": method,
    }
