# Docking redocking panel (multi-complex)

Ground truth source: **real PDB co-crystal structures** fetched on demand from
the SSRF-safe fixed RCSB origin. This is a pose-reproduction benchmark: each
curated crystal ligand is docked back into its frozen receptor and the top-pose
heavy-atom RMSD vs the crystal pose is measured.

## Contract

- `redock_panel.json` — 10 curated complexes (4 marked `essential` for
  pose-difficulty) with predeclared success criteria and explicit limitations.
- `run_redock_panel.py` — runs the *same* docking code path the production API
  uses (`app.tools.docking.run_vina` / `compute_pocket_grid`): fpocket grid,
  obabel pH-7.4 PDBQT prep, Vina exhaustiveness 32 / 9 modes / fixed seed,
  RDKit symmetry-aware heavy-atom RMSD (`GetBestRMS`).

## Honesty rule (never negotiable)

If AutoDock Vina, OpenBabel or fpocket are not present, the runner writes an
explicit `status: not_executed / reason: requires_external` record and exits 2.
It **never** reports a pass without actually reproducing a crystal pose. A
`requires_external` record is an explicitly not-benchmarked status, and the
matrix keeps DOCK-REDOCK unclaimed until the panel genuinely passes.

## Run

```bash
python benchmark/fixtures/docking/run_redock_panel.py
```

Result: `benchmark/results/docking/redock/latest.json` (schema
`bionexus-redock-panel/v1`).