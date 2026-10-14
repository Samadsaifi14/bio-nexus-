# Docking integrity repair and verification — 2026-10-12

## Changes

- Pin SHA-256 checksums for official AutoDock Vina 1.2.7 Linux x86_64 and Windows assets. Check fresh downloads, cached files, installed files and memoized paths before execution. Publish downloads atomically only after verification. Verify Vina in all three Docker build paths.
- Reject missing receptor coordinates and nonfinite coordinates instead of returning an origin center. Require explicit finite three-component grids and positive finite sizes before launching Vina. Result validation also rejects missing or nonfinite grid evidence.
- Repair the benchmark tool lookup, convert receptors to PDBQT, select one crystal ligand residue, and convert each docked PDBQT pose to SDF. Restore the known ligand graph after nonpolar hydrogen merging while preserving docked coordinates.
- Measure symmetry-aware heavy-atom RMSD using RDKit CalcRMS in the receptor frame. GetBestRMS aligns the ligand and can conceal translation errors, so it is unsuitable for this pose-recovery gate.
- Retain dated execution reports, source PDBs, prepared inputs, Vina logs/poses, raw and reconstructed top-pose SDFs, tool information and artifact SHA-256 hashes. Add regression tests to scientific-integrity CI and a manual live canonical-evidence workflow. Redirect the legacy canonical script to the repaired runner.

## Measured evidence

| Check | Result |
| --- | --- |
| Targeted regression suite | 62 passed: binary integrity, grid validation, RMSD, runner preparation, result validation and log parsing |
| Canonical 1STP-BTN redocking | PASS: top pose RMSD **0.8285105611879668 Å**, threshold ≤2.0 Å |
| Canonical settings | Vina 1.2.7; seed 42; exhaustiveness 32; 9 poses; fpocket top pocket |
| Grid center / size (Å) | [10.566, 2.844, -10.458] / [29.805, 29.514, 29.442] |
| Full ten-complex panel | FAILED: 1/10; nine fixtures lack the declared ligand in their PDB structure |

The canonical result supports pose reproduction for this one complex. The
ten-complex panel remains unvalidated. No general pose accuracy, affinity
accuracy or screening-enrichment claim follows from this control.

Evidence: `benchmark/results/docking/canonical/latest.json` and
`benchmark/results/docking/redock/latest.json`, with dated reports and retained
artifacts beside them. Initial diagnostic failures remain in dated reports;
the latest records contain the completed evaluations.

Runtime: Python 3.12.14, RDKit 2026.09.1, Open Babel executable reporting 3.1.0
(wheel 3.1.1.23), fpocket source tag 4.2.3 / commit
`4bb0d8447f62fee77e2c3c29f54b5fcaf5e2c066`, compiled locally with GCC 13.3.
This is a local scientific run; the Docker images and newly added GitHub Actions
workflow have not been executed here. The broader API smoke suite was stopped
after hanging during shared application initialization; no pass is claimed for it.

## Binary pins

Hashes were calculated from the official HTTPS release assets on 2026-10-12.
The release API had null digest fields, so these are retained-byte integrity
pins, not publisher-signed attestations.

| Asset | SHA-256 |
| --- | --- |
| vina_1.2.7_linux_x86_64 | f31f774f723bba7bbe6e9d1c47577020eea9a8da16424284c043d22593570644 |
| vina_1.2.7_win.exe | e0c4b2715e0c1a74f6e92d0f3be0328ac97542eafbc111e6b1efad897a73cce5 |

Sources: [official Vina release](https://github.com/ccsb-scripps/AutoDock-Vina/releases/tag/v1.2.7),
[RDKit CalcRMS documentation](https://www.rdkit.org/docs/source/rdkit.Chem.rdMolAlign.html#rdkit.Chem.rdMolAlign.CalcRMS).

## Repeat

```bash
PYTHONPATH=bioai-platform/backend python benchmark/fixtures/docking/run_redock_panel.py \
  --canonical --outdir benchmark/results/docking/canonical
```

Requires Vina 1.2.7 matching the pin, Open Babel, fpocket, RDKit and the backend
imports. The manual `Canonical docking redocking evidence` workflow installs
these dependencies, runs the control and uploads its evidence even on failure.

## Follow-up verification

The focused integrity, engine, RMSD and runner regression suite was rerun: **42 passed**. The live-source attempt `20261012T081150513726Z` stopped before docking because the configured SOCKS proxy dependency was unavailable; its diagnostic report is retained. Canonical run `20261012T081218306850Z` then used the retained 1STP source after verifying its SHA-256 against the prior source manifest, and executed Vina again: **PASS**, RMSD **0.8285105611879668 Å**. All ten retained artifact hashes were verified after this run. This rerun confirms docking execution against the retained source; it does not reverify live RCSB retrieval.
