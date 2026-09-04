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

_INTERPRO_SEARCH_URL = "https://www.ebi.ac.uk/interpro/service/rest/iprscan5/run"
_INTERPRO_ENTRY_API = "https://www.ebi.ac.uk/interpro/api/entry/interpro/{accession}/?format=json"
_RCSB_SEQUENCE_API = "https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/1"
_RCSB_FASTA_API = "https://www.rcsb.org/fasta/entry/{pdb_id}"

METHOD_VERSION = "interpro2go-evidence-v1"


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

def _run_interproscan(sequence: str, timeout: int = 120) -> list[dict]:
    """Submit a protein sequence to the configured InterProScan REST service.

    Returns domain/entry hits. An empty list means that no usable evidence was
    obtained; callers must not reinterpret service failure as biological
    evidence for absence of function.
    """
    import time

    body = json.dumps({"sequences": [{"sequence": sequence}], "type": "PROTEIN"})
    req = urllib.request.Request(
        _INTERPRO_SEARCH_URL,
        data=body.encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=30)  # nosemgrep
        job_data = json.loads(resp.read())
        job_id = job_data.get("jobId", "")
        if not job_id:
            return []
    except Exception as exc:
        logger.warning("InterProScan submit failed: %s", exc)
        return []

    status_url = f"https://www.ebi.ac.uk/interpro/service/rest/iprscan5/status/{job_id}"
    result_url = f"https://www.ebi.ac.uk/interpro/service/rest/iprscan5/result/{job_id}/json"

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status_resp = urllib.request.urlopen(status_url, timeout=15)  # nosemgrep
            status = json.loads(status_resp.read()).get("status", "")
        except Exception:
            time.sleep(3)
            continue

        if status == "FINISHED":
            break
        if status in ("FAILED", "ERROR"):
            logger.warning("InterProScan job %s status: %s", job_id, status)
            return []
        time.sleep(3)
    else:
        logger.warning("InterProScan job %s timed out", job_id)
        return []

    try:
        result_resp = urllib.request.urlopen(result_url, timeout=30)  # nosemgrep
        results = json.loads(result_resp.read())
    except Exception as exc:
        logger.warning("InterProScan result fetch failed: %s", exc)
        return []

    hits: list[dict] = []
    for entry in results.get("results", []):
        accession = entry.get("accession", "")
        name = entry.get("name", "")
        database = entry.get("database", "")
        for match in entry.get("matches", []):
            for loc in match.get("locations", []):
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

def predict_function(pdb_id: str) -> dict:
    """Infer GO terms for a PDB entry from InterPro2GO evidence.

    If no InterPro2GO evidence is available, the function returns an explicit
    `insufficient_evidence` state. It does not fabricate GO terms from sequence
    composition.
    """
    sequence = _fetch_pdb_sequence(pdb_id)
    if not sequence:
        raise RuntimeError(f"No sequence available for PDB {pdb_id}")

    domain_hits = _run_interproscan(sequence)
    go_terms = _interpro_to_go(domain_hits) if domain_hits else []

    if go_terms:
        status = "inferred"
        method = "interpro2go"
        note = (
            "GO terms are inferred from InterPro entry-to-GO mappings. They are not direct "
            "experimental annotations for this protein and no calibrated probability is reported."
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
        "ec_scope_note": (
            "EC-number inference is not implemented in the research-grade function module; "
            "no EC number is returned unless a separately validated method is added."
        ),
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
            "sequence_source": "RCSB PDB",
            "domain_source": "InterProScan",
            "go_mapping_source": "InterPro2GO via InterPro API",
            "retrieval_is_live": True,
        },
        "note": note,
    }
