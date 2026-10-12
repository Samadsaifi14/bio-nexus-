"""Standalone BLAST execution for dedicated BLAST jobs.

The dedicated BLAST UI must return the search result itself. It must not route a
nucleotide search through the downstream protein-annotation pipeline, where a
valid blastn/blastx/tblastx result could be masked by unrelated UniProt, MSA,
structure, or interpretation failures.
"""

from app.routers.pipeline_v2 import _run_blast
from app.services.sequence_utils import detect_sequence_type


async def run_blast_only(
    sequence: str,
    *,
    status_callback=None,
    fast_mode: bool = False,
    blast_params: dict | None = None,
) -> dict:
    """Run only BLAST and return the canonical result context.

    A completed search with zero hits is a valid scientific outcome and is
    returned as ``status=complete`` by the worker. Provider/transport failures
    remain errors and are not converted into biological no-hit claims.
    """
    blast_params = blast_params or {}
    result = await _run_blast(
        sequence,
        status_callback=status_callback,
        fast_mode=fast_mode,
        blast_params=blast_params,
    )

    if result.get("error") or result.get("search_complete") is False:
        raise RuntimeError(result.get("error") or "BLAST provider did not complete the search")

    seq_type = detect_sequence_type(sequence)
    context = {
        "sequence": sequence,
        "length": len(sequence),
        "query": {
            "sequence": sequence,
            "length": len(sequence),
            "sequence_type": seq_type,
        },
        "blast": result,
    }

    query_accession = (blast_params.get("query_accession") or "").strip()
    if query_accession:
        context["query"]["accession"] = query_accession

    return context
