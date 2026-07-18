from Bio import SeqIO
from io import StringIO
from typing import Optional


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
    return "ncbi"


async def map_refseq_to_uniprot(refseq_id: str) -> str | None:
    import httpx

    is_refseq = refseq_id[:3] in ("NP_", "XP_", "YP_", "WP_", "AP_")
    sources = ["RefSeq_Protein"] if is_refseq else ["RefSeq_Protein", "EMBL", "PDB"]

    for source in sources:
        url = "https://rest.uniprot.org/idmapping/uniprotkb/search"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json={
                    "from": source,
                    "to": "UniProtKB",
                    "ids": refseq_id,
                })
                if resp.status_code != 200:
                    continue
                data = resp.json()
                results = data.get("results") or []
                if results:
                    mapped = results[0].get("to", {}).get("primaryAccession", "")
                    if mapped:
                        return mapped
        except Exception:
            pass
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
