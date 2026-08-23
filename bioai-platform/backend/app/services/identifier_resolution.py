"""Multi-database identifier resolution to UniProt.

Turns any BLAST hit accession, gene name, or raw protein sequence into a
UniProt accession so downstream analyses (UniProt lookup, InterPro domains,
AlphaFold, secondary structure, Ramachandran) work for essentially every
query, regardless of which database the BLAST hit came from.

Resolution strategies, cheapest first:

1. Already a UniProt accession (Swiss-Prot / TrEMBL) -> use directly.
2. ``xref:<id>`` search on UniProtKB REST API (synchronous, ~1s). Matches
   cross-references to RefSeq, GenBank, EMBL, PDB, Ensembl, CCDS, etc.
3. Reviewed full-text search on the BLAST hit description.
4. EBI NCBI BLAST of the raw query sequence against UniProtKB (Swiss-Prot,
   falling back to Swiss-Prot+TrEMBL). The top hit's accession *is* the
   UniProt accession. Works for any sequence with no known identifier.
5. UniProt ID-mapping queue (asynchronous, slow — only as a last resort)
   with correct ``/idmapping/status`` polling.
"""
from __future__ import annotations

import asyncio
import logging
import re

import httpx

logger = logging.getLogger(__name__)

UNIPROT_BASE = "https://rest.uniprot.org"
UNIPROT_SEARCH = f"{UNIPROT_BASE}/uniprotkb/search"
IDMAPPING_RUN = f"{UNIPROT_BASE}/idmapping/run"
IDMAPPING_STATUS = f"{UNIPROT_BASE}/idmapping/status/{{job_id}}"
IDMAPPING_RESULTS = f"{UNIPROT_BASE}/idmapping/uniprotkb/results/{{job_id}}"

# Swiss-Prot: [OPQ]xxxxxxx OR TrEMBL: A0Axxxxxxxx
UNIPROT_RE = re.compile(r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|A0A[A-Z0-9]{5,}[0-9])$")


def is_uniprot_accession(acc: str | None) -> bool:
    acc = (acc or "").strip().upper()
    return bool(UNIPROT_RE.match(acc))


def extract_organism(description: str | None) -> str:
    """Pull the trailing ``[Homo sapiens]`` organism from an NCBI description."""
    m = re.search(r"\[([^\[\]]+)\]$", (description or "").strip())
    return m.group(1).strip() if m else ""


def extract_gene_hint(description: str | None) -> str:
    """Best-effort gene-symbol extraction from an NCBI protein description.

    NCBI descriptions have no single reliable format (``recName: ...;
    short=TP63``, ``gene=TP63``, ``tumor protein p63 isoform 1``), so this is
    only ever used as a hint for the name search — never a hard dependency.
    """
    desc = (description or "").strip()
    if not desc:
        return ""
    # Drop the trailing [Organism] tag — "Mus musculus" etc. is not a gene.
    desc = re.sub(r"\s*\[[^\[\]]*\]$", "", desc)
    m = re.search(r"gene[=:]\s*([A-Za-z0-9_-]+)", desc, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"\bshort[=:]\s*([A-Za-z0-9_-]{1,20})", desc)
    if m:
        return m.group(1)
    # A bare token that looks like a gene symbol (2-6 alphanumerics, not an
    # all-lowercase English word): gene names carry digits or mixed case
    # (p63, TP53, Polr2a) while protein-name words are plain lowercase.
    common_words = {
        "protein", "tumor", "factor", "receptor", "growth", "chain",
        "isoform", "subunit", "kinase", "family", "member", "domain",
        "precursor", "hypothetical", "predicted", "similar", "partial",
        "fragment", "transcription", "homolog", "homologue", "recombination",
    }
    for word in re.split(r"[\s,;:()\[\]|/-]+", desc):
        w = word.strip()
        if not w or w.lower() in common_words:
            continue
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9]{1,5}", w) and (w != w.lower() or any(c.isdigit() for c in w)):
            return w
    return ""


def _clean_fasta(seq: str) -> str:
    seq = (seq or "")
    # Drop a FASTA/header line if present (e.g. ">sp|P04637|TP53_HUMAN ...").
    if seq.lstrip().startswith(">"):
        seq = re.sub(r"^[^\n]*\n", "", seq)
    return "".join(c for c in seq if c.isalpha()).upper()


_NT_CHARS = set("ACGTUN")


def _looks_nucleotide(seq: str) -> bool:
    """True when the sequence alphabet is ACGT(U)N-only (i.e. DNA/RNA)."""
    seq = (seq or "").upper().replace("-", "").replace(".", "")
    return bool(seq) and set(seq).issubset(_NT_CHARS) and any(c in "ACGTU" for c in seq)


async def _get_json(client: httpx.AsyncClient, url: str, params: dict | None = None) -> dict | None:
    try:
        resp = await client.get(url, params=params)
        if resp.status_code == 200:
            return resp.json()
    except Exception as exc:
        logger.debug("GET %s failed: %s", url, exc)
    return None


def _pick_best(result_rows: list[dict]) -> str | None:
    """Prefer a reviewed (Swiss-Prot) hit, else the first hit."""
    if not result_rows:
        return None
    for row in result_rows:
        # "UniProtKB reviewed (Swiss-Prot)" vs "UniProtKB unreviewed (TrEMBL)"
        if (row.get("entryType") or "").startswith("UniProtKB reviewed"):
            acc = row.get("primaryAccession", "")
            if acc:
                return acc
    acc = result_rows[0].get("primaryAccession", "")
    return acc or None


async def search_uniprot(
    query: str,
    *,
    size: int = 3,
    reviewed: bool = False,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    params: dict = {"query": query, "format": "json", "size": size}
    if reviewed:
        params["query"] = f"({query}) AND reviewed:true"

    async def _fetch(c: httpx.AsyncClient) -> dict | None:
        return await _get_json(c, UNIPROT_SEARCH, params)

    if client is not None:
        data = await _fetch(client)
    else:
        async with httpx.AsyncClient(timeout=15) as c:
            data = await _fetch(c)
    if not data:
        return []
    return data.get("results") or []


async def resolve_by_xref(accession: str, client: httpx.AsyncClient | None = None) -> str | None:
    """Map any cross-referenced ID (RefSeq, GenBank, PDB, Ensembl, ...) to UniProt."""
    acc = (accession or "").strip().upper()
    if not acc:
        return None
    # Drop a PDB chain suffix ("4X0Z:A" -> "4X0Z"); xref search only indexes
    # the parent entry.
    if ":" in acc:
        head = acc.split(":", 1)[0]
        if head:
            acc = head
    if is_uniprot_accession(acc):
        return acc
    try:
        rows = await search_uniprot(f"xref:{acc}", size=5, reviewed=True, client=client)
        mapped = _pick_best(rows)
        if mapped:
            return mapped
        rows = await search_uniprot(f"xref:{acc}", size=5, client=client)
        return _pick_best(rows)
    except Exception as exc:
        logger.debug("xref resolution failed for %s: %s", acc, exc)
        return None


async def resolve_by_name(
    description: str,
    *,
    organism: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """Reviewed full-text search on a protein description / gene hint."""
    if not description or not description.strip():
        return None
    text = description.strip()
    # Drop the trailing [organism] — it is not part of the protein name and
    # breaks the full-text search with an unmatched bracket.
    text = re.sub(r"\s*\[[^\[\]]*\]$", "", text)
    text = text.split(";")[0].split(" OS=")[0].strip()[:120]
    # Neutralize query-breaking characters that some NCBI/EBI descriptions
    # carry (quotes, backslashes, unbalanced brackets) so arbitrary hit text
    # can never produce an invalid UniProt search query.
    text = re.sub(r'["\\{}\[\]()]', " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 4:
        return None
    try:
        # NOTE: unquoted full-text search matches UniProt protein names far
        # better than an exact quoted phrase (isoform suffixes, synonyms...).
        if organism:
            rows = await search_uniprot(
                f"{text} AND organism_name:\"{organism}\" AND reviewed:true",
                size=5,
                client=client,
            )
        else:
            rows = await search_uniprot(f"{text} AND reviewed:true", size=5, client=client)
        if rows:
            mapped = _pick_best(rows)
            if mapped:
                return mapped
        # Retry without the reviewed filter (fragments / unreviewed orthologs)
        if organism:
            rows = await search_uniprot(f"{text} AND organism_name:\"{organism}\"", size=5, client=client)
        else:
            rows = await search_uniprot(text, size=5, client=client)
        if rows:
            mapped = _pick_best(rows)
            if mapped:
                return mapped
        # Last resort: search by gene symbol when the name text is ambiguous.
        gene_hint = extract_gene_hint(description)
        if gene_hint and gene_hint.lower() not in text.lower():
            if organism:
                rows = await search_uniprot(
                    f"gene:{gene_hint} AND organism_name:\"{organism}\" AND reviewed:true",
                    size=5,
                    client=client,
                )
            else:
                rows = await search_uniprot(f"gene:{gene_hint} AND reviewed:true", size=5, client=client)
            return _pick_best(rows)
        return None
    except Exception as exc:
        logger.debug("name resolution failed for %r: %s", description[:80], exc)
        return None


async def resolve_by_sequence(sequence: str) -> str | None:
    """Run EBI BLAST of the query sequence against UniProtKB.

    The top hit's accession is a UniProt accession, so this resolves any
    sequence even when no identifier or gene name is known.  Hits are gated
    by e-value so low-complexity regions (which BLAST matches spuriously)
    don't produce a garbage accession.  Bounded to ~4 min worst case.
    """
    seq = _clean_fasta(sequence)
    if len(seq) < 15:
        return None
    # Protein BLAST can't take a nucleotide query — and a nucleotide sequence
    # has no UniProt protein identity anyway. Bail out so we never submit a
    # nonsense blastp job.
    if _looks_nucleotide(seq):
        logger.debug("sequence fallback skipped: nucleotide query")
        return None
    try:
        from app.tools.blast import BlastTool

        tool = BlastTool()
        for database in ("uniprotkb_swissprot", "uniprotkb"):
            # Bound each fallback search; the pipeline already ran BLAST once,
            # so this only needs to be fast enough to confirm identity.
            tool.MAX_POLL_TIME = 120
            try:
                result = await tool.run_uncached({
                    "sequence": seq,
                    "program": "blastp",
                    "database": database,
                    "max_hits": 5,
                })
            except Exception as exc:
                logger.debug("EBI BLAST (%s) failed: %s", database, exc)
                continue
            if result.get("error") or not result.get("hits"):
                logger.debug("EBI BLAST (%s) returned no hits", database)
                continue
            best: str | None = None
            for hit in result["hits"]:
                acc = (hit.get("accession") or "").strip().upper()
                if not acc:
                    continue
                try:
                    evalue = float(hit.get("evalue", 1e10))
                except (TypeError, ValueError):
                    evalue = 1e10
                if evalue > 1e-5:
                    continue
                if is_uniprot_accession(acc):
                    return acc
                if best is None:
                    best = acc
            if best:
                return best
    except Exception as exc:
        logger.debug("sequence resolution failed: %s", exc)
    return None


async def resolve_by_id_mapping(accession: str) -> str | None:
    """UniProt ID-mapping queue — slow; used only as a final fallback.

    Cheap because the ``xref:<id>`` search already covers most of these
    databases in ~1s; this only catches stragglers.
    """
    acc = (accession or "").strip()
    if not acc:
        return None
    sources = ["RefSeq_Protein", "Ensembl", "EMBL"]
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            for source in sources:
                try:
                    submit = await client.post(
                        IDMAPPING_RUN,
                        data={"from": source, "to": "UniProtKB", "ids": acc},
                    )
                    if submit.status_code != 200:
                        continue
                    job_id = (submit.json() or {}).get("jobId", "")
                    if not job_id:
                        continue
                    for _ in range(20):
                        await asyncio.sleep(1)
                        st = await client.get(IDMAPPING_STATUS.format(job_id=job_id))
                        if st.status_code != 200:
                            break
                        job_status = (st.json() or {}).get("jobStatus")
                        if job_status == "ERROR":
                            break
                        if job_status != "FINISHED":
                            continue
                        res = await client.get(IDMAPPING_RESULTS.format(job_id=job_id))
                        if res.status_code == 200:
                            results = (res.json() or {}).get("results") or []
                            for entry in results:
                                mapped = (entry.get("to") or {}).get("primaryAccession", "")
                                if mapped:
                                    return mapped
                        break
                except Exception as exc:
                    logger.debug("ID mapping (%s) failed for %s: %s", source, acc, exc)
    except Exception as exc:
        logger.debug("ID mapping client error for %s: %s", acc, exc)
    return None


# Confidence tiers per resolution method (techspec.md §1.1):
#   tiers 1–3 (direct/xref/name) → identified — exact database identity
#   tiers 4–5 (sequence/idmapping) → homolog — inferred via a similar sequence
_CONFIDENCE_BY_METHOD = {
    "direct": "identified",
    "xref": "identified",
    "name": "identified",
    "sequence": "homolog",
    "idmapping": "homolog",
}

UNRESOLVED_RESULT = {
    "accession": None,
    "method": "de_novo",
    "status": "unresolved",
    "confidence": "de_novo",
}


def _resolved(accession: str, method: str) -> dict:
    return {
        "accession": accession,
        "method": method,
        "status": "resolved",
        "confidence": _CONFIDENCE_BY_METHOD.get(method, "homolog"),
    }


async def resolve_to_uniprot(
    accession: str | None = None,
    sequence: str | None = None,
    description: str | None = None,
    organism: str | None = None,
    try_sequence: bool = True,
) -> dict:
    """Resolve any identifier/sequence to a UniProt accession.

    Runs strategies cheapest-first; when all five exhaust, returns an
    explicit unresolved result (tier 6, techspec.md §1) instead of None so
    callers can route to the de novo characterization branch.

    Returns ``{"accession": str|None, "method": str, "status":
    "resolved"|"unresolved", "confidence": "identified"|"homolog"|"de_novo"}``.
    Methods: direct / xref / name / sequence / idmapping / de_novo.
    """
    acc = (accession or "").strip()
    if is_uniprot_accession(acc):
        return _resolved(acc.upper(), "direct")

    async with httpx.AsyncClient(timeout=20) as client:
        if acc:
            mapped = await resolve_by_xref(acc, client=client)
            if mapped:
                return _resolved(mapped, "xref")

        if description:
            mapped = await resolve_by_name(description, organism=organism, client=client)
            if mapped:
                return _resolved(mapped, "name")

    if try_sequence and sequence:
        mapped = await resolve_by_sequence(sequence)
        if mapped:
            return _resolved(mapped, "sequence")

    if acc:
        mapped = await resolve_by_id_mapping(acc)
        if mapped:
            return _resolved(mapped, "idmapping")

    return dict(UNRESOLVED_RESULT)
