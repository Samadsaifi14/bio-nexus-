# Final observed repair verification — 18 October 2026

## Completed and deployed code repairs

Source: ae77a4fe1b9e55f2a5c7034009952f4a9a5bade2.

- Corrected nine PDB/ligand/protein identity mismatches in the ten-complex redocking fixture against RCSB deposited records. PDB IDs, essential flags, first-pocket policy and thresholds were preserved.
- Corrected the benchmark's stale artifact contract: native poses come from result_pdbqt; result_sdf is a separate real SDF export. Missing or inconsistent pose counts fail explicitly.
- Four artifact-contract regressions passed.
- Source PDBs, ligand inventories, selected instances, fixture revision and checksums are retained for failures and successes.
- Security scan (Semgrep, both CodeQL languages, dependency audit), frontend build, fixture integrity, focused interpretation/statistics regressions, full-reference local BLAST and RNA-seq R CI passed.
- Deployment run 39066715499 verified public frontend and exact healthy backend source ae77a4fe1b9e55f2a5c7034009952f4a9a5bade2.

## Executed docking outcome

Run: https://github.com/Samadsaifi14/bio-nexus-/actions/runs/39066715524

Canonical 1STP-BTN control passed: top-pose symmetry-aware heavy-atom RMSD **0.8561054622533372 A**, nine native poses.

The complete unchanged-threshold panel **FAILED: 2/10** against the required 70% plus essential-control criterion:

| PDB | Result |
|---|---|
| 1STP | PASS, 0.8561054622533372 A |
| 1IEP | First pocket misses crystal site, offset 59.0 A |
| 1HVR | PASS, 0.5148776764816382 A |
| 2F12 | First pocket misses crystal site, offset 10.1 A |
| 1GKC | First pocket misses crystal site, offset 19.4 A |
| 1OYT | Docked-pose SDF parsing failed |
| 1UYG | Reference-ligand SDF parsing failed |
| 2H4G | FAIL, RMSD 7.366091769207125 A |
| 1Q4T | First pocket misses crystal site, offset 19.5 A |
| 1P62 | First pocket misses crystal site, offset 9.7 A |

Raw run records, parameters, code/reference/tool fingerprints and per-artifact hashes are in verification/2026-10-18-docking-execution.json. Retained Actions artifacts include source structures, prepared receptors/ligands, native poses and logs. The archive records immutable Actions artifact digests. These are redocking results, not affinity accuracy.

The preparation and first-pocket policy were not changed after observing outcomes. These failures require a separately declared and evaluated preparation/site-selection repair; changing which pocket the benchmark accepts after seeing the answer would not establish blind-docking performance.

## Broad audit and external availability

The completed pre-docking-repair source bb2fe6b99048cb4e3efcede9ca97a774dbca33f4 audit had **1,534 passed, 3 failed, 40 skipped** (run 39065969753; job 117493595002). Failures: one EBI test exceeded its CI 90-second cap; the NCBI loop and consecutive-reliability tests failed with estimated queue 9,563 seconds. Local Swiss-Prot recovery passed independently and is never substituted for nr/nt scope.

The newer full audit at ae77 is run 39066715514. Its actual final outcome must be read from that run; the earlier counts are not a result for ae77. Live tests were neither removed nor weakened.

## Unfinished acceptance items

- Eight of ten redocking panel cases failed as listed above. Canonical success does not close the multi-complex acceptance item.
- Live remote BLAST availability is not under application control; unsupported scopes still depend on their named providers.
- The execution workspace remains disconnected. Attached lecture slides/count-file copies and authenticated browser workflows were not inspected.
- Long MD/convergence, production-scale RNA-seq/variant truth-set execution and matched competitor benchmarks remain bounded by their separate contracts in SCIENTIFIC_ROADMAP_STATUS.md. No all-feature parity, experimental accuracy or clinical validation claim is made.

This is an evidence hand-off, not an assertion that all requested work is complete.
