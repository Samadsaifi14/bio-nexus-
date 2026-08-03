"""
Fetch a full sequence by accession.

Primary source is NCBI efetch; UniProt is used as a fallback for accessions
that NCBI does not know (e.g. UniProt-only ids). Both lookups are ttl_cache'd
for 24h since sequences are immutable.
"""

from __future__ import annotations

import re

import httpx

from app.services.cache import ttl_cache
from app.services.ncbi_service import NCBIService

UNIPROT_FASTA_BASE = "https://rest.uniprot.org/uniprotkb"
VALID_SOURCES = ("auto", "ncbi", "uniprot")


def _sanitize_accession(accession: str) -> str:
    accession = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", accession or "").strip()
    return accession.upper()


def _parse_first_fasta(text: str) -> tuple[str, str] | None:
    """Return (accession, sequence) for the first FASTA record, or None."""
    lines = text.splitlines()
    if not lines or not lines[0].startswith(">"):
        return None
    header = lines[0][1:].strip()
    accession = header.split()[0] if header.split() else header
    seq = "".join(
        l.strip()
        for l in lines[1:]
        if l.strip() and not l.strip().startswith(">")
    )
    seq = re.sub(r"[^A-Za-z]", "", seq)
    if not seq:
        return None
    return accession, seq


class SequenceFetchService:
    @ttl_cache(ttl=86400, prefix="uniprot_fasta")
    async def fetch_uniprot_fasta(self, accession: str) -> dict:
        url = f"{UNIPROT_FASTA_BASE}/{accession}.fasta"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers={"Accept": "text/plain"})
        if resp.status_code != 200 or not resp.text.strip():
            return {"error": f"UniProt returned HTTP {resp.status_code} for {accession}"}
        parsed = _parse_first_fasta(resp.text)
        if not parsed:
            return {"error": f"UniProt FASTA parse failed for {accession}"}
        acc, seq = parsed
        return {
            "accession": acc,
            "sequence": seq,
            "length": len(seq),
        }


_ncbi = NCBIService()
_uniprot = SequenceFetchService()


async def fetch_sequence_by_accession(accession: str, source: str = "auto") -> dict:
    """Fetch a full sequence by accession.

    source: ``auto`` (NCBI efetch first, UniProt fallback), ``ncbi``, or ``uniprot``.
    Returns ``{"sequence": ...}`` on success, or ``{"error": ...}`` on failure.
    """
    accession = _sanitize_accession(accession)
    if not accession:
        return {"error": "No accession provided"}
    source = (source or "auto").lower()
    if source not in VALID_SOURCES:
        return {"error": f"Invalid source '{source}' (expected auto|ncbi|uniprot)"}

    if source in ("auto", "ncbi"):
        ncbi = await _ncbi.fetch_by_accession(accession)
        if ncbi.get("sequence"):
            return {
                "accession": ncbi.get("accession") or accession,
                "source": "ncbi",
                "sequence": ncbi["sequence"],
                "length": ncbi.get("length", len(ncbi["sequence"])),
                "organism": ncbi.get("organism", ""),
                "description": ncbi.get("description", ""),
            }

    if source in ("auto", "uniprot"):
        uni = await _uniprot.fetch_uniprot_fasta(accession)
        if uni.get("sequence"):
            return {
                "accession": uni.get("accession") or accession,
                "source": "uniprot",
                "sequence": uni["sequence"],
                "length": uni.get("length", len(uni["sequence"])),
            }

    return {
        "error": (
            f"Could not retrieve sequence for accession '{accession}' from NCBI or "
            "UniProt. The ID may be dead/obsolete, or the lookup was rate-limited."
        )
    }
