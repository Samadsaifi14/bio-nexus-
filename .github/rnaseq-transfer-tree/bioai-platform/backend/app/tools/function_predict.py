"""Conservative protein-function inference from InterPro2GO mappings.

BioNexus does not train a function-prediction model in this module. The
research-grade path implemented here is deliberately narrower:

1. Fetch the protein sequence represented by the requested PDB entry.
2. Run InterProScan on that sequence.
3. Map InterPro entries to Gene Ontology (GO) terms through the InterPro API.
4. Report the mapping provenance and amount of supporting domain evidence.

The previous implementation converted domain-hit counts and simple amino-acid
composition thresholds into probability-like "confidence" percentages. Those
numbers were not calibrated probabilities and therefore are not suitable for a
research result. They have been removed. If InterProScan/InterPro2GO does not
provide evidence, BioNexus returns no GO prediction and exposes sequence
composition only as a descriptive measurement.

EC-number inference is intentionally out of scope until a defensible,
benchmarked mapping/prediction method is implemented.
"""

from __future__ import annotations

import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

_INTERPRO_ENTRY_API = "https://www.ebi.ac.uk/interpro/api/entry/interpro/{accession}/?format=json"
_RCSB_SEQUENCE_API = "https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/1"
_RCSB_FASTA_API = "https://www.rcsb.org/fasta/entry/{pdb_id}"

METHOD_VERSION = "interpro2go-evidence-v1"

_EC_SCOPE_NOTE = (
    "EC-number inference is not implemented in the research-grade function module; "
    "no EC number is returned unless a separately validated method is added."
)

# Retrieval failures recorded by the live InterProScan/InterPro2GO calls. A lookup
# that failed is a different scientific claim than a lookup that succeeded and found
# no mapping, so the two must not collapse into the same reported state.
_RETRIEVAL_FAILURES: list[str] = []


def _record_retrieval_failure(reason: str) -> None:
    if reason not in _RETRIEVAL_FAILURES:
        _RETRIEVAL_FAILURES.append(reason)


# ---------------------------------------------------------------------------
# Sequence fetching
# ---------------------------------------------------------------------------

def _fetch_pdb_sequence(pdb_id: str) -> str:
    """Fetch the canonical amino-acid sequence exposed for a PDB entry."""
    url = _RCSB_SEQUENCE_API.format(pdb_id=pdb_id)
    try:
        data = json.loads(urllib.request.urlopen(url, timeout=15).read())  # nosemgrep
        return data.get("entity_poly", {}).get("pdbx_seq_one_letter_code_can", "")
    except Exception:
        pass

    try:
        url = _RCSB_FASTA_API.format(pdb_id=pdb_id)
        text = urllib.request.urlopen(url, timeout=15).read().decode()  # nosemgrep
        lines = [line for line in text.splitlines() if not line.startswith(">")]
        return "".join(lines).replace("\n", "")
    except Exception as exc:
        raise RuntimeError(f"Could not fetch sequence for {pdb_id}: {exc}") from exc


# ---------------------------------------------------------------------------
# InterProScan sequence search
# ---------------------------------------------------------------------------

def _run_interproscan(sequence: str, timeout: int = 90) -> list[dict]:
    """Submit a protein sequence to the InterProScan REST service and return hits.

    InterProScan 5 is retired by EBI and its REST endpoint 404s, so this targets
    InterProScan 6 at the EBI Tools REST path. Note the v6 API is *not* the v5
    JSON ``{"sequences": ...}`` shape used previously: submission is form-encoded
    and returns a plain-text job id, and status is plain text, not JSON.

    Returns domain/entry hits. An empty list means no usable evidence was
    obtained; every failure path records itself via ``_record_retrieval_failure``
    so callers report ``evidence_unavailable`` rather than biological absence.

    ``timeout`` is deliberately short. This helper is synchronous and inlined in a
    request path, while the EBI job needs 7-20+ minutes; on timeout the failure is
    recorded honestly and the caller degrades to "evidence unavailable". Callers
    that can afford to wait should use the async job client in
    ``app.services.de_novo`` instead.
    """
    import time
    from urllib.parse import urlencode

    from app.services.ssrf import validate_url

    base = "https://www.ebi.ac.uk/Tools/services/rest/iprscan6"
    try:
        validate_url(f"{base}/run")
    except Exception as exc:
        logger.warning("InterProScan URL rejected by SSRF policy: %s", exc)
        _record_retrieval_failure(f"InterProScan endpoint rejected: {exc}")
        return []

    body = urlencode(
        {
            "email": "bioflow@example.com",
            "stype": "protein",
            "sequence": "".join(c for c in (sequence or "") if c.isalpha()).upper(),
        }
    ).encode()
    req = urllib.request.Request(
        f"{base}/run",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "text/plain"},
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=30)  # nosemgrep
        job_id = resp.read().decode().strip()
        if not job_id:
            _record_retrieval_failure("InterProScan submission returned no job id")
            return []
    except Exception as exc:
        logger.warning("InterProScan submit failed: %s", exc)
        _record_retrieval_failure(f"InterProScan submission failed: {type(exc).__name__}: {exc}")
        return []

    status_url = f"{base}/status/{job_id}"
    result_url = f"{base}/result/{job_id}/json"

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status_resp = urllib.request.urlopen(status_url, timeout=15)  # nosemgrep
            status = status_resp.read().decode().strip()
        except Exception:
            time.sleep(3)
            continue

        if status == "FINISHED":
            break
        if status in ("FAILED", "ERROR", "NOT_FOUND"):
            logger.warning("InterProScan job %s status: %s", job_id, status)
            _record_retrieval_failure(f"InterProScan job {job_id} ended with status {status}")
            return []
        time.sleep(3)
    else:
        logger.warning("InterProScan job %s did not finish within %ss", job_id, timeout)
        _record_retrieval_failure(
            f"InterProScan job {job_id} did not finish within the {timeout}s in-request budget; "
            "it is still running upstream. This is a retrieval failure, not an absence of domains."
        )
        return []

    try:
        result_resp = urllib.request.urlopen(result_url, timeout=30)  # nosemgrep
        results = json.loads(result_resp.read())
    except Exception as exc:
        logger.warning("InterProScan result fetch failed: %s", exc)
        _record_retrieval_failure(f"InterProScan result fetch failed: {type(exc).__name__}: {exc}")
        return []

    # v6 keeps the v5 results -> matches -> locations shape.
    hits: list[dict] = []
    blocks = results.get("results", []) if isinstance(results, dict) else (results or [])
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        for match in block.get("matches", []) or []:
            sig = match.get("signature", {}) or {}
            entry = sig.get("entry", {}) or {}
            lib = (sig.get("signatureLibraryRelease") or {}).get("library", "")
            accession = entry.get("accession") or sig.get("accession", "")
            name = entry.get("name") or sig.get("name") or ""
            database = entry.get("sourceDatabase") or lib or ""
            for loc in match.get("locations", []) or []:
                hits.append({
                    "accession": accession,
                    "name": name,
                    "database": database,
                    "start": loc.get("start", 0),
                    "end": loc.get("end", 0),
                    "score": loc.get("score"),
                })

    hits.sort(key=lambda hit: (hit.get("start", 0), hit.get("end", 0)))
    return hits


# ---------------------------------------------------------------------------
# InterPro -> GO mapping
# ---------------------------------------------------------------------------

def _fetch_interpro_go_terms(accession: str) -> list[dict]:
    """Fetch GO terms associated with one InterPro entry.

    These are database mappings associated with InterPro entries. They are not
    automatically equivalent to direct experimental evidence for the queried
    protein, so the output is labelled `interpro2go_mapping` rather than
    `experimentally_validated`.
    """
    url = _INTERPRO_ENTRY_API.format(accession=accession)
    try:
        resp = urllib.request.urlopen(url, timeout=15)  # nosemgrep
        data = json.loads(resp.read())
    except Exception as exc:
        logger.warning("InterPro GO lookup failed for %s: %s", accession, exc)
        _record_retrieval_failure(
            f"InterPro entry lookup failed for {accession}: {type(exc).__name__}: {exc}"
        )
        return []

    terms: list[dict] = []
    namespace_map = {"F": "MF", "P": "BP", "C": "CC"}
    for go in data.get("metadata", {}).get("go_terms", []):
        go_id = go.get("id", "")
        if not go_id:
            continue
        category = go.get("category", "")
        terms.append({
            "id": go_id,
            "name": go.get("name", ""),
            "category": namespace_map.get(category, category),
        })
    return terms


def _interpro_to_go(hits: list[dict]) -> list[dict]:
    """Aggregate InterPro2GO mappings while preserving evidence provenance."""
    accessions: dict[str, int] = {}
    for hit in hits:
        accession = hit.get("accession")
        if accession:
            accessions[accession] = accessions.get(accession, 0) + 1

    aggregated: dict[str, dict] = {}
    for accession, hit_count in accessions.items():
        for go in _fetch_interpro_go_terms(accession):
            record = aggregated.setdefault(
                go["id"],
                {
                    "go_id": go["id"],
                    "name": go["name"],
                    "namespace": go["category"],
                    "supporting_interpro_entries": [],
                    "supporting_domain_hits": 0,
                },
            )
            if accession not in record["supporting_interpro_entries"]:
                record["supporting_interpro_entries"].append(accession)
            record["supporting_domain_hits"] += hit_count

    terms: list[dict] = []
    for record in aggregated.values():
        entries = sorted(record["supporting_interpro_entries"])
        terms.append({
            **record,
            "supporting_interpro_entries": entries,
            "support_count": len(entries),
            "evidence_type": "interpro2go_mapping",
            "source": "InterPro",
            "source_url": "https://www.ebi.ac.uk/interpro/",
            "confidence": None,
            "confidence_note": (
                "No calibrated probability is reported. Support count is the number of "
                "distinct InterPro entries mapping this sequence to the GO term."
            ),
        })

    terms.sort(
        key=lambda term: (
            -term["support_count"],
            -term["supporting_domain_hits"],
            term["go_id"],
        )
    )
    return terms


# ---------------------------------------------------------------------------
# Descriptive sequence measurements
# ---------------------------------------------------------------------------

def _amino_acid_composition(sequence: str) -> dict:
    seq_upper = sequence.upper()
    seq_len = len(seq_upper)
    counts: dict[str, int] = {}
    for aa in seq_upper:
        counts[aa] = counts.get(aa, 0) + 1
    return {
        "aa": "ACDEFGHIKLMNPQRSTVWY",
        "fractions": {
            aa: round(counts.get(aa, 0) / max(seq_len, 1), 4)
            for aa in "ACDEFGHIKLMNPQRSTVWY"
        },
    }


def _residue_chemistry_scores(sequence: str) -> list[float]:
    """Return a descriptive residue-class score, not model saliency.

    The score is retained only to support the existing visualization while the
    UI migrates to the research-grade schema. It must never be interpreted as
    feature attribution or causal residue importance.
    """
    values: list[float] = []
    for aa in sequence.upper():
        if aa in "DEKRH":
            value = 0.6
        elif aa in "STNQ":
            value = 0.4
        elif aa in "AGV":
            value = 0.2
        else:
            value = 0.15
        values.append(round(value, 3))
    return values


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _clean_sequence(sequence: str) -> str:
    return "".join(c for c in (sequence or "") if c.isalpha()).upper()


def _hits_from_scan(scan: dict) -> list[dict]:
    """Normalize an InterProScan domains payload to the research-grade hit shape."""
    hits: list[dict] = []
    for domain in (scan.get("domains") or []):
        if not isinstance(domain, dict):
            continue
        hits.append({
            "accession": domain.get("accession", ""),
            "name": domain.get("name", ""),
            "database": domain.get("source_db") or domain.get("database", ""),
            "start": domain.get("start", 0),
            "end": domain.get("end", 0),
            "score": domain.get("score"),
        })
    hits.sort(key=lambda hit: (hit.get("start", 0), hit.get("end", 0)))
    return hits


def _prediction(sequence: str, pdb_id: str, domain_hits: list[dict],
                retrieval_failures: list[str]) -> dict:
    """Build the research-grade prediction payload from sequence and InterPro hits."""
    retrieval_failures = list(retrieval_failures or [])
    retrieval_failures += [f for f in _RETRIEVAL_FAILURES if f not in retrieval_failures]

    go_terms = _interpro_to_go(domain_hits) if domain_hits else []

    if go_terms:
        status = "inferred"
        method = "interpro2go"
        note = (
            "GO terms are inferred from InterPro entry-to-GO mappings. They are not direct "
            "experimental annotations for this protein and no calibrated probability is reported."
        )
    elif retrieval_failures:
        status = "evidence_unavailable"
        method = "interpro2go_retrieval_failed"
        note = (
            "InterProScan/InterPro2GO retrieval did not complete, so no GO mapping could be read: "
            + "; ".join(retrieval_failures)
            + ". This is a retrieval failure, not evidence that the protein has no InterPro2GO "
            "mapping. BioNexus does not substitute composition heuristics for a function "
            "prediction in research-grade mode."
        )
    else:
        status = "insufficient_evidence"
        method = "interpro2go_no_evidence"
        note = (
            "No InterPro2GO-supported GO term was obtained. BioNexus does not substitute "
            "composition heuristics for a function prediction in research-grade mode."
        )

    composition = _amino_acid_composition(sequence)
    chemistry_scores = _residue_chemistry_scores(sequence)

    return {
        "pdb_id": pdb_id.upper(),
        "sequence_length": len(sequence),
        "status": status,
        "go_terms": go_terms,
        "ec_numbers": [],
        "ec_scope_note": _EC_SCOPE_NOTE,
        "domain_hits": [
            {
                "accession": hit.get("accession", ""),
                "name": hit.get("name", ""),
                "database": hit.get("database", ""),
                "start": hit.get("start", 0),
                "end": hit.get("end", 0),
                "score": hit.get("score"),
            }
            for hit in domain_hits
        ],
        # Backward-compatible field: intentionally empty so clients do not present
        # residue chemistry as model saliency/feature attribution.
        "saliency": [],
        "residue_chemistry_scores": chemistry_scores,
        "residue_chemistry_note": (
            "Descriptive residue-class scores only; not model saliency or feature importance."
        ),
        "composition": composition,
        "method": method,
        "method_version": METHOD_VERSION,
        "provenance": {
            "sequence_source": (
                "RCSB PDB" if pdb_id.lower() != "de_novo" else "user-submitted sequence"
            ),
            "domain_source": "InterProScan",
            "go_mapping_source": "InterPro2GO via InterPro API",
            "retrieval_is_live": not retrieval_failures,
            "retrieval_failures": retrieval_failures,
        },
        "note": note,
    }


def _running_marker(scan: dict, sequence: str, pdb_id: str) -> dict:
    """Explicit "not yet" payload for a scan that is still running upstream."""
    return {
        "pdb_id": pdb_id.upper(),
        "sequence_length": len(sequence),
        "status": "running",
        "interpro_job_id": scan.get("interpro_job_id"),
        "go_terms": [],
        "ec_numbers": [],
        "ec_scope_note": _EC_SCOPE_NOTE,
        "domain_hits": [],
        "saliency": [],
        "residue_chemistry_scores": _residue_chemistry_scores(sequence),
        "residue_chemistry_note": (
            "Descriptive residue-class scores only; not model saliency or feature importance."
        ),
        "composition": _amino_acid_composition(sequence),
        "method": "interpro2go",
        "method_version": METHOD_VERSION,
        "provenance": {
            "sequence_source": "user-submitted sequence",
            "domain_source": "InterProScan",
            "go_mapping_source": "InterPro2GO via InterPro API",
            "retrieval_is_live": True,
            "retrieval_failures": [],
        },
        "note": (
            "InterProScan 6 is still running; GO terms will be computed when the "
            "background job finishes."
        ),
    }


async def _predict_from_sequence(sequence: str, pdb_id: str = "de_novo") -> dict:
    """Run InterProScan 6 on a raw sequence and return a function prediction.

    Waits at most ``INLINE_WAIT_BUDGET_S`` (see ``app.services.de_novo``). If the
    EBI job is still running it returns an explicit ``running`` marker carrying the
    job id; ``prediction_from_result`` completes it on the background poller.
    """
    seq = _clean_sequence(sequence)
    if not seq:
        raise ValueError("Empty sequence")

    from app.services.de_novo import interpro_sequence_search

    failures: list[str] = []
    try:
        scan = await interpro_sequence_search(sequence)
    except Exception as exc:
        logger.warning("De novo function search failed: %s", exc)
        failures.append(f"InterProScan submission failed: {type(exc).__name__}: {exc}")
        scan = {"status": "failed", "domains": [], "error": str(exc)}

    if scan.get("status") == "running":
        return _running_marker(scan, seq, pdb_id)

    if scan.get("status") != "complete":
        failures.append(scan.get("error") or "InterProScan job did not complete")

    # Sequence-mode GO mapping reuses the worker's retrieval-failure ledger.
    # Function predictions are rare, and this clear runs immediately before the
    # mapping below, so cross-job provenance races are not a practical concern.
    _RETRIEVAL_FAILURES.clear()
    return _prediction(seq, pdb_id, _hits_from_scan(scan), failures)


def prediction_from_result(result: dict, sequence: str, pdb_id: str = "de_novo") -> dict:
    """Finish a function prediction from an InterProScan job that completed later."""
    seq = _clean_sequence(sequence)
    _RETRIEVAL_FAILURES.clear()
    failures: list[str] = []
    if result.get("status") != "complete":
        failures.append(result.get("error") or "InterProScan job did not complete")
    return _prediction(seq, pdb_id, _hits_from_scan(result), failures)


def predict_function(pdb_id: str) -> dict:
    """Infer GO terms for a PDB entry from InterPro2GO evidence.

    If no InterPro2GO evidence is available, the function returns an explicit
    `insufficient_evidence` state. It does not fabricate GO terms from sequence
    composition.
    """
    _RETRIEVAL_FAILURES.clear()

    sequence = _fetch_pdb_sequence(pdb_id)
    if not sequence:
        raise RuntimeError(f"No sequence available for PDB {pdb_id}")

    domain_hits = _run_interproscan(sequence)
    return _prediction(sequence, pdb_id, domain_hits, _RETRIEVAL_FAILURES)
