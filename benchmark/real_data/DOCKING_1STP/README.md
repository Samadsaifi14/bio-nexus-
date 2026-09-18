# BBS1 canonical docking redocking benchmark — 1STP / biotin

This directory contains the executable benchmark for the predeclared
`BBS1-DOCK-1STP-BTN` fixture.

The benchmark downloads RCSB PDB entry **1STP**, retains protein `ATOM`
records as the receptor, extracts the crystallographic `BTN` ligand, defines
the docking box from the crystallographic ligand heavy-atom centroid, prepares
the receptor and ligand through Open Babel/PDBQT, and runs AutoDock Vina with
the fixed protocol recorded by
`app.benchmarking.docking_redock.canonical_redocking_fixture()`.

Acceptance is **symmetry-aware heavy-atom pose RMSD <= 2.0 Å**. The threshold
must not be relaxed after seeing the result. A failed or unavailable execution
does not support a pose-accuracy claim.

The GitHub Actions workflow `.github/workflows/docking-1stp-redocking.yml`
retains the input structure, prepared receptor/ligand, Vina log, predicted
best pose, environment information, SHA-256 values, and `summary.json` as a
workflow artifact. The benchmark is separate from production scoring so an
affinity score cannot be confused with redocking accuracy.


## Retained execution result

GitHub Actions run `35389973834` executed the predeclared protocol and
completed successfully. The retained best pose had a **0.7252 Å**
symmetry-aware heavy-atom RMSD, below the predeclared **2.0 Å** acceptance
threshold (16 ligand heavy atoms). AutoDock Vina 1.2.7 produced 20 poses with
seed 42 and exhaustiveness 32; the best reported affinity was -6.373 kcal/mol.

The retained workflow artifact is `docking-1stp-redocking` (artifact ID
`10565356302`; artifact ZIP SHA-256
`7844d5f217a2c7105ca4c022a2b18667e2fc085dd10df2ee8fcb1db26fbacba2`).
The compact committed record is `retained_run_manifest.json`.

This establishes pose recovery for this one benchmark fixture only. The Vina
affinity is not validated by the RMSD result, and the result does not establish
general docking accuracy, superiority, clinical validity, or performance for
other receptor-ligand systems. The GitHub artifact is retention-limited, so a
persistent archival deposit is still required for final publication packaging.
