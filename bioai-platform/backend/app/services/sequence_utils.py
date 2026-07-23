from Bio import SeqIO
from io import StringIO
from typing import Optional

UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"


def detect_sequence_type(seq: str) -> str:
    clean = seq.upper().replace("-", "").replace(".", "").replace(" ", "")
    if not clean:
        return "unknown"
    protein_chars = set("ACDEFGHIKLMNPQRSTVWYUBZXOJ")
    dna_chars = set("ACGTN")
    rna_chars = set("ACGUN")
    seq_set = set(clean)
    extra_chars = seq_set - protein_chars
    if not extra_chars:
        return "protein"
    if seq_set.issubset(rna_chars):
        if "U" in seq_set and "T" not in seq_set:
            return "rna"
    if seq_set.issubset(dna_chars):
        return "dna"
    if seq_set.issubset(dna_chars | {"U"}):
        return "rna"
    return "unknown"


def detect_input_format(text: str) -> str:
    text = text.strip()
    if text.startswith(">"):
        return "fasta"
    if text.startswith("LOCUS") or text.startswith("DEFINITION"):
        return "genbank"
    if text.startswith(("ATOM", "HETATM")) or (text.startswith("HEADER")):
        return "pdb"
    clean = "".join(c for c in text if c.isalpha()).upper()
    if not clean:
        return "unknown"
    seq_type = detect_sequence_type(clean)
    if seq_type != "unknown":
        return "raw_sequence"
    return "unknown"


def detect_source_from_accession(accession: str) -> str:
    import re
    acc = accession.strip().upper()
    if acc.startswith(("NP_", "XP_", "YP_", "WP_", "AP_", "NM_", "XM_", "NR_", "XR_")):
        return "ncbi"
    if acc.startswith("UPI"):
        return "uniparc"
    if re.match(r"^[OPQ][0-9][A-Z0-9]{3}[0-9]$", acc):
        return "uniprot"
    if re.match(r"^A0A[A-Z0-9]{5,}[0-9]$", acc):
        return "uniprot"
    if re.fullmatch(r'[A-Za-z0-9]{4}', acc):
        return "pdb"
    return "ncbi"


async def map_refseq_to_uniprot(refseq_id: str) -> str | None:
    import httpx
    import asyncio
    import logging

    logger = logging.getLogger(__name__)
    refseq_id = refseq_id.strip()

    # Skip if already a UniProt accession — no mapping needed
    if re.match(r"^[OPQ][0-9][A-Z0-9]{3}[0-9]$", refseq_id) or re.match(r"^A0A[A-Z0-9]{5,}[0-9]$", refseq_id):
        return refseq_id

    # Try direct UniProtKB lookup first (works for some cross-referenced IDs)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            url = f"{UNIPROT_BASE}/{refseq_id}"
            resp = await client.get(url, params={"format": "json"})
            if resp.status_code == 200:
                data = resp.json()
                acc = data.get("primaryAccession", "")
                if acc:
                    return acc
    except Exception:
        pass

    # ID mapping API — two-step: POST /idmapping/run, then GET /results/{jobId}
    # Try RefSeq_Protein first (most common for NP_/XP_/YP_ accessions)
    is_refseq = refseq_id[:3] in ("NP_", "XP_", "YP_", "WP_")
    sources = ["RefSeq_Protein"] if is_refseq else ["RefSeq_Protein", "EMBL", "GenBank", "PDB"]

    for source in sources:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Step 1: submit mapping job
                submit = await client.post(
                    "https://rest.uniprot.org/idmapping/run",
                    data={"from": source, "to": "UniProtKB", "ids": refseq_id},
                )
                if submit.status_code != 200:
                    logger.debug("ID mapping submit failed for %s (source=%s): %s", refseq_id, source, submit.status_code)
                    continue
                job_id = submit.json().get("jobId", "")
                if not job_id:
                    continue

                # Step 2: poll for results (up to 15s)
                for _ in range(15):
                    await asyncio.sleep(1)
                    result = await client.get(
                        f"https://rest.uniprot.org/idmapping/uniprotkb/results/{job_id}",
                    )
                    if result.status_code == 200:
                        data = result.json()
                        results_list = data.get("results") or []
                        if results_list:
                            mapped = results_list[0].get("to", {}).get("primaryAccession", "")
                            if mapped:
                                logger.info("Mapped %s -> %s via %s", refseq_id, mapped, source)
                                return mapped
                        # No results yet or empty — check if still processing
                        if not results_list and "jobId" in str(data):
                            continue
                        break
                    elif result.status_code == 404:
                        # Still processing
                        continue
                    else:
                        logger.debug("ID mapping poll failed for %s: %s", refseq_id, result.status_code)
                        break
        except Exception as e:
            logger.debug("ID mapping error for %s (source=%s): %s", refseq_id, source, e)
            pass

    logger.warning("Could not map %s to UniProt via any source", refseq_id)
    return None


def validate_sequence(sequence: str) -> dict:
    result = {
        "valid": False,
        "sequence_type": "unknown",
        "format": "unknown",
        "length": 0,
        "issues": [],
    }
    if not sequence or not sequence.strip():
        result["issues"] = ["Empty sequence"]
        return result
    seq_format = detect_input_format(sequence)
    result["format"] = seq_format
    if seq_format == "fasta":
        try:
            records = list(SeqIO.parse(StringIO(sequence), "fasta"))
            if not records:
                result["issues"] = ["FASTA format detected but no records parsed"]
                return result
            concat_seq = str(records[0].seq)
            result["length"] = len(concat_seq)
            result["sequence_type"] = detect_sequence_type(concat_seq)
            if len(concat_seq) < 6:
                result["issues"] = [f"Sequence too short: {len(concat_seq)} residues"]
                return result
            result["valid"] = True
        except Exception as e:
            result["issues"] = [f"FASTA parse error: {str(e)}"]
        return result
    clean = "".join(c for c in sequence if c.isalpha()).upper()
    if not clean:
        result["issues"] = ["No valid sequence characters found"]
        return result
    result["length"] = len(clean)
    result["sequence_type"] = detect_sequence_type(clean)
    if result["length"] < 6:
        result["issues"] = [f"Sequence too short: {result['length']} residues"]
        return result
    valid_protein = set("ACDEFGHIKLMNPQRSTVWYUBZXOJ")
    extra = set(clean) - valid_protein
    if extra and result["sequence_type"] == "protein":
        invalid_chars = [c for c in sorted(extra) if c not in "BZX"]
        if invalid_chars:
            result["issues"] = [f"Unusual characters for protein sequence: {', '.join(invalid_chars)}"]
    result["valid"] = len(result["issues"]) == 0
    return result
