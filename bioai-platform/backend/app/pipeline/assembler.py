from typing import Any


class ContextAssembler:
    def assemble(
        self,
        sequence: str,
        blast_result: dict,
        uniprot_result: dict | None,
        alphafold_result: dict | None,
    ) -> dict:
        context = {
            "query": {
                "sequence": sequence,
                "length": len([c for c in sequence if c.isalpha()]),
            },
            "blast": self._summarize_blast(blast_result),
            "uniprot": self._summarize_uniprot(uniprot_result) if uniprot_result else None,
            "alphafold": alphafold_result,
        }
        return context

    def _summarize_blast(self, blast_result: dict) -> dict:
        hits = blast_result.get("hits", [])
        summary = {
            "count": len(hits),
            "source": blast_result.get("source", "EBI BLAST"),
            "database": blast_result.get("database", "swissprot"),
        }
        if hits:
            best = hits[0]
            summary["top_hit"] = {
                "accession": best.get("accession", ""),
                "description": best.get("description", ""),
                "evalue": best.get("evalue", 0),
                "identity_pct": best.get("identity_pct", 0),
                "bit_score": best.get("bit_score", 0),
                "alignment_length": best.get("alignment_length", 0),
            }
            summary["hits"] = [
                {
                    "accession": h.get("accession", ""),
                    "description": h.get("description", ""),
                    "evalue": h.get("evalue", 0),
                    "identity_pct": h.get("identity_pct", 0),
                    "bit_score": h.get("bit_score", 0),
                }
                for h in hits[:10]
            ]
        return summary

    def _summarize_uniprot(self, uniprot_result: dict) -> dict:
        return {
            "accession": uniprot_result.get("accession", ""),
            "full_name": uniprot_result.get("full_name", ""),
            "organism": uniprot_result.get("organism", ""),
            "gene_names": uniprot_result.get("gene_names", []),
            "functions": uniprot_result.get("functions", []),
            "keywords": uniprot_result.get("keywords", []),
            "subcellular_locations": uniprot_result.get("subcellular_locations", []),
            "pdb_ids": uniprot_result.get("pdb_ids", []),
            "features": [
                f for f in (uniprot_result.get("features", []) or [])
                if f.get("type") in ("ACTIVE_SITE", "BINDING", "MUTAGENESIS")
            ],
            "go_terms": uniprot_result.get("go_terms", []),
            "sequence_length": uniprot_result.get("sequence_length", 0),
        }
