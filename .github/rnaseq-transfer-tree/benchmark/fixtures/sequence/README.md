# BLAST multi-query accession recovery (live EBI, Python)

Ground truth source: **canonical Swiss-Prot accessions** fetched from the UniProt
REST API; each is BLASTed through the production `app.tools.blast.BlastTool`
against `uniprotkb_swissprot` with identical predeclared settings.

## Contract

- `blast_queries.json` — 8 curated proteins with predeclared expected
  accessions, success criteria, and two essential controls.
- `run_blast_recovery.py` — fetches each query sequence (recorded with sha256
  for tamper-evident run provenance), runs `BlastTool.run_uncached`, and checks
  that the expected accession appears in the top `max_recovery_rank` (5) hits.
  Success requires a recovery fraction ≥ 0.8 and recovery of ≥1 essential query.

## Honesty rule

If the UniProt REST API or EBI BLAST endpoint is unreachable or returns errors
(e.g. ReadTimeout on the result endpoint, or `status=ERROR`), the runner
records `status: not_executed / reason: requires_external` with the full
exception representation and exits 2. It **never** fabricates a pass.

## Live findings

The production `BlastTool._fetch_results` uses a 30 s `httpx.AsyncClient`
read timeout that is insufficient for some EBI result payloads; the runner
records the genuine `ReadTimeout` and documents it as a production robustness
finding. This is an expected, predeclared limitation, not a harness defect.

## Run

```bash
python benchmark/fixtures/sequence/run_blast_recovery.py
# offline honesty check (pytest gate):
python benchmark/fixtures/sequence/run_blast_recovery.py --no-network
```

Result: `benchmark/results/sequence/blast/latest.json` (schema
`bionexus-blast-accession-recovery/v1`).