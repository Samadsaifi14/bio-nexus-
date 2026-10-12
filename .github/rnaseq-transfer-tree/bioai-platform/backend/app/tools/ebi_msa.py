"""Validated client for EMBL-EBI Job Dispatcher multiple-sequence alignment services.

The remote services remain authoritative for the alignment they return. BioNexus
validates the input and verifies that the output preserves the complete record
set and every ungapped residue before accepting it. A remote failure is exposed
as a failure/fallback event; it is never converted into a fabricated alignment.
"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx

logger = logging.getLogger(__name__)

EBI_TOOLS: dict[str, str] = {
    "clustalo": "https://www.ebi.ac.uk/Tools/services/rest/clustalo",
    "muscle": "https://www.ebi.ac.uk/Tools/services/rest/muscle",
    "kalign": "https://www.ebi.ac.uk/Tools/services/rest/kalign",
    "mafft": "https://www.ebi.ac.uk/Tools/services/rest/mafft",
    "tcoffee": "https://www.ebi.ac.uk/Tools/services/rest/tcoffee",
}

POLL_INTERVAL = 1
MAX_POLLS = 60
TREE_TYPES = ["phylotree"]
EBI_FALLBACK_ORDER = ["clustalo", "muscle"]
_RUNNING_STATUSES = {"RUNNING", "PENDING", "QUEUED"}
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
_DNA_IUPAC = set("ACGTRYSWKMBDHVN")
_PROTEIN_IUPAC = set("ACDEFGHIKLMNPQRSTVWYBXZJUO")


def _parse_fasta(sequence: str, *, stype: str, allow_gaps: bool) -> list[tuple[str, str]]:
    if stype not in ("protein", "dna"):
        raise ValueError("stype must be 'protein' or 'dna'")
    alphabet = _PROTEIN_IUPAC if stype == "protein" else _DNA_IUPAC
    if allow_gaps:
        alphabet = set(alphabet) | {"-", "."}

    records: list[tuple[str, str]] = []
    seen: set[str] = set()
    current_id: str | None = None
    current: list[str] = []

    def flush() -> None:
        nonlocal current_id, current
        if current_id is None:
            return
        seq = "".join(current).replace(" ", "").upper()
        if not seq:
            raise ValueError(f"FASTA record {current_id!r} is empty")
        bad = sorted(set(seq) - alphabet)
        if bad:
            raise ValueError(
                f"FASTA record {current_id!r} contains characters invalid for {stype}: {', '.join(bad)}"
            )
        records.append((current_id, seq.replace(".", "-") if allow_gaps else seq))
        current_id = None
        current = []

    for line_no, raw in enumerate((sequence or "").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            flush()
            header = line[1:].strip()
            if not header:
                raise ValueError(f"FASTA header at line {line_no} has no identifier")
            current_id = header.split()[0]
            if not _SAFE_ID.fullmatch(current_id):
                raise ValueError(f"FASTA identifier {current_id!r} is not alignment/tree safe")
            if current_id in seen:
                raise ValueError(f"Duplicate FASTA identifier: {current_id}")
            seen.add(current_id)
        else:
            if current_id is None:
                raise ValueError(f"FASTA sequence appears before a header at line {line_no}")
            current.append("".join(line.split()))
    flush()

    if len(records) < 2:
        raise ValueError("Multiple sequence alignment requires at least two FASTA records")
    return records


def validate_msa_input(sequence: str, stype: str) -> list[tuple[str, str]]:
    """Validate unaligned MSA input and return normalized records."""
    return _parse_fasta(sequence, stype=stype, allow_gaps=False)


def _validate_alignment(source_fasta: str, aligned_fasta: str, stype: str) -> dict:
    source = validate_msa_input(source_fasta, stype)
    aligned = _parse_fasta(aligned_fasta, stype=stype, allow_gaps=True)
    source_map = dict(source)
    aligned_map = dict(aligned)

    if set(source_map) != set(aligned_map) or len(source) != len(aligned):
        missing = sorted(set(source_map) - set(aligned_map))
        extra = sorted(set(aligned_map) - set(source_map))
        raise ValueError(f"EBI MSA changed the record set (missing={missing}, extra={extra})")

    lengths = {len(seq) for seq in aligned_map.values()}
    if len(lengths) != 1:
        raise ValueError("EBI MSA returned aligned rows of unequal length")

    for sid, original in source_map.items():
        if aligned_map[sid].replace("-", "") != original:
            raise ValueError(f"EBI MSA output did not preserve residues for {sid!r}")

    return {
        "sequence_count": len(source),
        "alignment_length": next(iter(lengths)),
        "record_set_verified": True,
        "residue_preservation_verified": True,
    }


async def run_ebi_msa_best_effort(
    sequence: str,
    stype: str = "protein",
    email: str = "bioflow@example.com",
    tools: list[str] | None = None,
) -> dict:
    """Try the declared EBI providers in order, preserving fallback provenance."""
    validate_msa_input(sequence, stype)
    tools = tools or EBI_FALLBACK_ORDER
    errors: list[str] = []
    for index, tool in enumerate(tools):
        base_url = EBI_TOOLS.get(tool)
        if not base_url:
            errors.append(f"unknown tool {tool!r}")
            continue
        try:
            result = await run_ebi_msa(
                base_url=base_url,
                sequence=sequence,
                stype=stype,
                email=email,
            )
            result["method"] = tool
            result["provider_fallback_index"] = index
            result["provider_fallback"] = index > 0
            return result
        except Exception as exc:
            errors.append(f"{tool}: {exc}")
            logger.warning("EBI MSA tool %s failed (%s); trying next", tool, exc)
    raise ValueError("EBI MSA failed on all tools: " + " | ".join(errors))


async def run_ebi_msa(
    base_url: str,
    sequence: str,
    stype: str = "protein",
    email: str = "bioflow@example.com",
) -> dict:
    """Submit FASTA to one EBI MSA service and verify the returned alignment."""
    validate_msa_input(sequence, stype)
    normalized_base = base_url.rstrip("/")
    if normalized_base not in EBI_TOOLS.values():
        raise ValueError("Unrecognized EMBL-EBI MSA service endpoint")
    method = normalized_base.rsplit("/", 1)[-1]

    async with httpx.AsyncClient(timeout=30) as client:
        submit_resp = await client.post(
            f"{normalized_base}/run",
            data={"email": email, "stype": stype, "sequence": sequence},
            headers={"Accept": "text/plain"},
        )
        if submit_resp.status_code != 200:
            detail = submit_resp.text[:200] if submit_resp.text else "no response body"
            raise ValueError(f"EBI submission failed (HTTP {submit_resp.status_code}): {detail}")
        job_id = submit_resp.text.strip()
        if not job_id or any(ch.isspace() for ch in job_id):
            raise ValueError("EBI submission returned an invalid job identifier")
        logger.info("EBI MSA job submitted (%s): %s", method, job_id)

        final_status = None
        for _ in range(MAX_POLLS):
            await asyncio.sleep(POLL_INTERVAL)
            try:
                status_resp = await client.get(f"{normalized_base}/status/{job_id}")
            except httpx.HTTPError as exc:
                logger.warning("EBI status poll failed: %s", exc)
                continue
            if status_resp.status_code != 200:
                raise ValueError(f"EBI status endpoint returned HTTP {status_resp.status_code}")
            status = status_resp.text.strip().upper()
            logger.info("EBI MSA status (%s/%s): %s", method, job_id, status)
            if status == "FINISHED":
                final_status = status
                break
            if status in _RUNNING_STATUSES:
                continue
            if not status:
                raise ValueError("EBI status endpoint returned an empty status")
            raise ValueError(f"EBI {method} job ended with status: {status}")
        if final_status != "FINISHED":
            raise ValueError(f"EBI {method} alignment timed out")

        fa_resp = await client.get(
            f"{normalized_base}/result/{job_id}/fa", headers={"Accept": "text/plain"}
        )
        if fa_resp.status_code != 200 or not fa_resp.text.strip():
            raise ValueError("Failed to fetch alignment result from EBI")
        aln_fasta = fa_resp.text
        validation = _validate_alignment(sequence, aln_fasta, stype)

        phylotree = ""
        for result_type in TREE_TYPES:
            try:
                tr = await client.get(
                    f"{normalized_base}/result/{job_id}/{result_type}",
                    headers={"Accept": "text/plain"},
                )
            except httpx.HTTPError:
                continue
            if tr.status_code == 200 and tr.text.strip():
                phylotree = tr.text
                break

    return {
        "job_id": job_id,
        "aln_fasta": aln_fasta,
        "phylotree": phylotree,
        "method": method,
        "provider": "EMBL-EBI Job Dispatcher",
        "service_url": normalized_base,
        "validation": validation,
    }
