# Attached audit: repairs and fresh verification

Follow-up: [2026-10-19 complete-case audit](../2026-10-19-complete-audit/REPORT.md). This dated report preserves the original failures and missing results; the follow-up records repairs and reruns.

Base: `dd807a31c309c45dfea5179fa4f123716d9e4296` (2026-10-18). The attachment is an audit, not evidence that all competitor capabilities are implemented. This patch repairs observed defects and preserves the remaining scope explicitly. **The entire roadmap is not complete or scientifically validated.**

## Repaired behavior

- PPI returns an explicit `interaction_count` and serializable partner records. Its prompt, browser evidence and export use recorded native STRING API 0–1 scores. Browser grounding accepts deterministic list lengths, rejects invented small integers, sign changes and unsupported percentage scaling, and excludes the top-level AI interpretation from its own evidence.
- Pairwise/BLAST/motif → dot plot sends sequences through one-shot tab-local storage. BLAST → motif also uses tab-local storage. Navigation URLs contain no sequence payloads. Docking explanatory copy renders only for docking.
- Editing an ADMET molecule, choosing an example or choosing a search hit clears prior results. A request generation guard prevents late responses from repopulating results for an earlier input. Generic charts require a recognized independent axis, preventing heterogeneous ADMET descriptor rows from becoming an inferred Min/Value plot; exact data remain in tables and JSON.
- Export, capture and InterPro mocked-HTTP tests opt into a public DNS fixture while still executing actual SSRF validation. A private-IP export test confirms the guard blocks before HTTP. This also fixes the zero-delay InterPro mocked polling loop that previously kept logging DNS failures until its process was terminated.
- Default `npm run build` uses webpack; `build:turbo` remains available. The final production build completes. No new lint errors; 120 existing warnings remain.
- Missing-tools docking regression now simulates missing tools in-process and writes only to its test directory. It cannot accidentally start a real panel or overwrite retained benchmark evidence on provisioned machines.
- Full-suite execution runs each of 140 modules in a separate process with per-test and module deadlines, JUnit/log retention, skips and failure reasons. Review-branch CI runs the audit, installs R/DESeq2/plotting dependencies, and retains module evidence. Updated CI has not been executed locally; local R remains absent.

## Docking: one metric repair, panel still fails

Built fpocket revision `4bb0d8447f62fee77e2c3c29f54b5fcaf5e2c066` and executed the entire panel twice with Vina/Open Babel/RDKit. The original path reproduced **2/10**, then the repaired native-coordinate path produced **3/10**. Acceptance remains top-pose heavy-atom RMSD **<2 Å**, at least **70%** panel success, and an essential-control success. No easier pocket, alternate pose or threshold was substituted.

The metric now transfers native Vina coordinates onto the prepared reference graph using stable atom serials. Reference-to-prepared correspondence uses original input coordinates, not a fit of the docked pose onto the crystal. Atom counts, elements, serial identities, finite coordinates and unambiguous correspondence are checked. Translation tests retain a 10 Å displacement; corrupt/missing atoms are rejected. The independently retained passing and failing controls retain their numerical values.

| Case | Fresh repaired outcome |
|---|---|
| 1STP | PASS, 0.8561054623 Å |
| 1IEP | FAIL, first pocket site offset 59.0 Å |
| 1HVR | PASS, 0.5148776765 Å |
| 2F12 | FAIL, first pocket site offset 10.1 Å |
| 1GKC | FAIL, first pocket site offset 19.4 Å |
| 1OYT | PASS native pose metric, 0.3208094450 Å; Open Babel SDF export still INVALID |
| 1UYG | FAIL, reference ligand SDF cannot be parsed |
| 2H4G | FAIL, 7.3660917692 Å |
| 1Q4T | FAIL, first pocket site offset 19.5 Å |
| 1P62 | FAIL, first pocket site offset 9.7 Å |

This repairs measurement of a valid native pose through an invalid pose-SDF conversion; it does not claim that conversion is fixed. `top_pose_chemical_graph.sdf` carries the validated reference graph and unchanged native pose coordinates. The invalid Open Babel export remains retained and explicitly flagged. The five site-selection misses, one reference-chemistry failure and one high-RMSD pose remain open. Redocking does not validate affinity prediction, screening enrichment or experimental binding.

## Verification and incomplete checks

- All **140/140 modules attempted** in isolated processes. Latest completed JUnit records contain **1,372 distinct passing tests and 20 skipped tests**. **197 collected cases lack a completed JUnit result** because feature validation (102), fuzz tests (71) and remote BLAST (24) exceeded their module deadlines. Partial dots from these modules are not counted as passes. There is no complete green aggregate.
- The initial de novo module process terminated; after the DNS-fixture repair, all **13 current tests pass**. `final-corrections.xml` retains the corrected 41-test group including fixture and native-mapping regressions. Original module outcomes remain in `execution.json` and the log archive, rather than being rewritten.
- Skips: 9 local native BLAST tests (binary/reference unavailable on this test PATH); 10 R-dependent numerical tests (R absent); 1 MD configuration guard (its deliberately unverified force-field branch has no applicable entry: the registry reports all combinations verified). Skips are excluded from passing test counts. Individual reasons are retained in `execution.json` and JUnit.
- Final webpack production build, frontend interpretation/private-handoff checks, RNA-seq plot checks, fixture integrity, TypeScript build checks and targeted backend regressions pass. Native short-MD modules execute with a 90-second per-test allowance and single-thread CPU settings; this does not establish long-time convergence or explicit-solvent production accuracy.
- Local production-frontend browser checks pass using HTTP-intercepted **native RDKit and Biopython fixture results**: ADMET example invalidation, stale-response rejection, pairwise copy scoping, and exact pairwise → dot plot transfer without URL sequences. This verifies UI behavior, not live external-provider or production deployment behavior.
- CLI browser setup hit truncated downloads and an unavailable Unix socket; a packaged Chromium and in-process Playwright run completed the checks. Screenshots were visually inspected. No production browser verification or deployment is claimed.

## Remaining work, explicitly open

All 26 original feature rows, module coverage and original scientific gaps are retained in `feature-status.json`. The docking, PPI and dot-plot rows carry current repair notes. Shared test-module counts overlap and must not be added across features.

Remaining requirements include production FASTQ/SEQC/GIAB workloads, broad/custom BLAST references and provider availability, the MSA editor and comparative feature overlays, executed external phylogeny/structure benchmarks, de novo motif validation, expanded sequence/primer specificity, protein preparation/protonation validation, complex prediction and homology-model execution, long MD/convergence, trained ADMET model validation, commercial pathway-provider terms, expert biological interpretation review and matched competitor workloads. None is marked completed by this patch. RNA-seq plot-layout issues and biological/provenance warnings in the earlier detailed audit remain open; absent local R prevents a fresh rendered numerical verification here.

## Retained evidence

- `latest-test-summary.json`: unique-case totals and missing-result counts.
- `execution.json`, `feature-status.json`: original isolated module outcomes, all skip reasons, all 26 feature rows and remaining scope.
- `final-corrections.xml`, `dns-regressions.xml`, `repair-regressions.xml`, `targeted.xml`: completed corrective checks; groups overlap.
- `redocking-baseline.json`, `redocking-repaired.json`: complete panel results, versions, input/code/artifact hashes and unchanged thresholds.
- `native-docking-artifacts.zip`: source structures, prepared inputs, native Vina poses/logs and valid/failed exports under `redocking/` and `redocking-repaired/`. Each result's relative `artifact_directory` resolves inside its corresponding archive folder.
- `test-logs.zip`: per-module logs/JUnit, build/lint checks and corrected regressions. The monolithic run's 857 MB repetitive log is represented by a labeled head/tail sample, source size and SHA-256, not a complete aggregate result.
- `browser-checks.json`, `admet-input-cleared.png`, `private-dotplot-handoff.png`: scoped browser checks and screenshots.

No experimental, clinical, all-roadmap or production-deployment success is claimed.
