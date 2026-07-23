from Bio import Entrez, SeqIO
from io import StringIO
from typing import Optional
from app.config import settings
from app.services.cache import ttl_cache

Entrez.email = "bioflow@example.com"


def _detect_db(accession: str) -> str:
    accession = accession.strip().upper()
    if accession.startswith(("NP_", "XP_", "YP_", "AP_", "WP_")):
        return "protein"
    if accession.startswith(("NM_", "XM_", "NR_", "XR_")):
        return "nucleotide"
    if accession.startswith("NG_"):
        return "nucleotide"
    if accession.startswith(("NC_", "NT_", "NW_")):
        return "nucleotide"
    if accession.startswith(("AC_", "AE_")):
        return "nucleotide"
    return "protein"


def _detect_sequence_type(seq: str) -> str:
    clean = seq.upper().replace("-", "").replace(".", "")
    if not clean:
        return "unknown"
    dna_chars = set("ACGTUN")
    rna_chars = set("ACGUN")
    protein_chars = set("ACDEFGHIKLMNPQRSTVWY")
    seq_set = set(clean)
    if seq_set.issubset(dna_chars):
        if seq_set.intersection({"T", "U"}):
            return "dna"
    if seq_set.issubset(rna_chars):
        return "rna"
    if seq_set.issubset(protein_chars):
        return "protein"
    if seq_set.issubset(dna_chars.union({"N"})):
        return "dna"
    return "unknown"


class NCBIService:
    @ttl_cache(ttl=86400, prefix="ncbi_seq")
    async def fetch_by_accession(self, accession: str) -> dict:
        accession = accession.strip().upper()
        db = _detect_db(accession)
        try:
            handle = Entrez.efetch(db=db, id=accession, rettype="fasta", retmode="text")
            fasta_text = handle.read()
            handle.close()
            if not fasta_text.strip():
                return {"error": f"Accession '{accession}' not found in NCBI"}
            record = SeqIO.read(StringIO(fasta_text), "fasta")
            seq_str = str(record.seq)
            seq_type = _detect_sequence_type(seq_str)
            desc = record.description
            header_parts = desc.split(" ", 1)
            acc_from_header = header_parts[0]
            description = header_parts[1] if len(header_parts) > 1 else ""
            organism = ""
            if "[" in desc and "]" in desc:
                organism = desc.split("[")[-1].rstrip("]")
            return {
                "accession": acc_from_header,
                "db_source": "ncbi",
                "database": db,
                "sequence_type": seq_type,
                "sequence": seq_str,
                "length": len(seq_str),
                "organism": organism,
                "description": description,
                "from_cache": False,
            }
        except Exception as e:
            return {"error": str(e)}

    @ttl_cache(ttl=86400, prefix="ncbi_search")
    async def search_by_name(self, term: str, db: str = "protein", max_results: int = 10) -> dict:
        try:
            handle = Entrez.esearch(db=db, term=term, retmax=max_results)
            result = Entrez.read(handle)
            handle.close()
            ids = result.get("IdList", [])
            if not ids:
                return {"error": f"No results found for '{term}'", "results": []}
            handle = Entrez.esummary(db=db, id=",".join(ids))
            summaries = Entrez.read(handle)
            handle.close()
            results = []
            for docsum in summaries:
                if hasattr(docsum, "items"):
                    results.append({
                        "accession": str(docsum.get("AccessionVersion", "")),
                        "title": str(docsum.get("Title", "")),
                        "organism": str(docsum.get("Organism", "")),
                        "length": int(docsum.get("Length", 0) or 0),
                    })
            return {"results": results, "count": len(results), "query": term}
        except Exception as e:
            return {"error": str(e)}
