# Structure preparation live E2E (raw input -> clean -> health -> pockets)

Ground truth source: **real PDB entries** fetched from the SSRF-safe RCSB
origin. Runs the entire production structure-prep chain end to end:

```
fetch (app.tools.structure_prep.fetch_pdb_text)
  -> chain health (detect_chain_health)
  -> cleanup (pymol_cleanup: pymol2 wheel, else Biopython fallback)
  -> pocket detection (run_fpocket)
```

## Contract

- `structure_prep_panel.json` — 3 curated PDB entries (a pocket-bearing
  control 1STP, a large oligomer 4HHB, a tiny minimal case 1CRN) with
  predeclared assertions and explicit limitations.
- `run_structure_prep_e2e.py` — records every entry's health/cleanup/pocket
  results and evaluates the predeclared assertions; never fabricates a pass.

## Honesty rule (never negotiable)

If the RCSB network or the fpocket binary is unavailable, the runner writes an
explicit `status: not_executed / reason: requires_external` record and exits 2
(per-entry traces are still kept when the network alone failed). Full
execution exits 0 only when **every** predeclared assertion passes; any
assertion failure is recorded visibly with exit 1.

`--no-network` is a pytest-only knob that forces the honest requires_external
path so the offline deterministic suite can gate the honesty contract without
outbound access.

## Run

```bash
python benchmark/fixtures/structure_prep/run_structure_prep_e2e.py
```

Result: `benchmark/results/structure_prep/latest.json` (schema
`bionexus-structure-prep-e2e/v1`).