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
