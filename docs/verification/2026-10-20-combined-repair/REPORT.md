# Combined repair and verification — 2026-10-20

The repair improves provider handling and adds a separately measured multi-pocket docking method. The benchmark remains **not all-pass**. Reported scores use the predeclared criteria: top-pose heavy-atom RMSD <2 Å, site offset <8 Å, at least 70% of the full panel passing, and at least one essential control passing.

## Changes

- RCSB structure retrieval validates PDB IDs and coordinate records, follows redirects, and makes four bounded attempts with backoff. The docking dependency now includes HTTPX SOCKS support for the managed proxy. Redocking fixture retrieval has the same retry and response validation behavior.
- NCBI requests reserve process-wide request-start slots to respect the 10-second limit. Accepted search IDs are retained; the client uses the actual remaining poll budget rather than abandoning every search above a fixed RTOE threshold, and it does not resubmit a queued search after timeout.
- The new V2 runner searches five fpocket candidates, prepares ligand chemistry from RCSB CCD data, evaluates every CCD-validated ligand copy after docking, supports explicit receptor-chain selection and a separately prepared Zn cofactor for 1GKC, and ranks poses using fixed-coordinate Vinardo scores. Score-only grids are centered on each generated pose with a 6 Å margin. Each terminal case is checkpointed.
- V1 benchmark thresholds and outcomes are not rewritten by V2.

## Focused verification

The focused offline suite completed with **87 passed, 0 failed, 0 skipped**. It covers transient RCSB failures, coordinate validation, NCBI request pacing and timeout contracts, multisite copy handling, CCD identity, cofactor preparation, pose-grid coverage, and Vina score parsing. `py_compile`, `git diff --check`, and the fixture-manifest check passed.

Five structures that had previously encountered RCSB proxy failures were retrieved and validated with coordinate records: 1OYT, 1P62, 1Q4T, 1UYG, and 2H4G. Their byte counts and SHA-256 hashes are in `rcsb-refetches.json`.

## V1 redocking

Fresh ten-case run `20261020T143826741765Z` recorded **3/10 passing**. Two cases could not prepare because Biopython was absent from that initial runtime. A two-case rerun with the dependency available completed both cases: 1UYG passed at 0.656 Å; 1IEP failed with 62.015 Å top-pose RMSD and a 59.032 Å site offset. Taken together, the ten cases have terminal outcomes across the full run and this supplement: **4/10 pass**. This combined count is not a single ten-case execution. Native inputs, poses, and logs are preserved in `benchmark/results/docking/redock-refresh-20261020/artifacts.zip` and `benchmark/results/docking/v1-dependency-rerun-20261020/artifacts.zip`.

| Complex | Site offset (Å) | Top-pose RMSD (Å) | Result |
|---|---:|---:|---|
| 1STP | 1.322 | 0.856 | PASS |
| 1IEP | 59.032 | 62.015 | FAIL |
| 1HVR | 0.490 | 0.515 | PASS |
| 2F12 | 10.122 | 3.251 | FAIL |
| 1GKC | 19.375 | 19.948 | FAIL |
| 1OYT | 2.424 | 0.321 | PASS |
| 1UYG | 4.135 | 0.656 | PASS |
| 2H4G | 1.371 | 7.366 | FAIL |
| 1Q4T | 19.533 | unavailable | FAIL; Vina timed out at 300 s |
| 1P62 | 9.692 | 13.187 | FAIL |

The V1 full-run JSON captured a source hash while `app/tools/docking.py` was being updated during execution. It records the post-update hash; the retrieval helper in the runner was already loaded before that update. The supplementary 1IEP/1UYG run records matching current source hashes. This provenance limitation is retained here rather than presenting the full run as an uninterrupted single-source execution.

## V2 multi-pocket comparison

The first 2F12 diagnostic searched five pockets but did not recover the crystal pose: its best Vinardo-ranked pose was 5.232 Å RMSD. It also exposed two runner issues that were repaired before the full comparison: Vina may return fewer than the requested maximum number of distinct modes, and score-only may fail when the docked pose falls outside the original search grid. The runner now verifies that each pocket produced at least one scored pose and uses a pose-centered scoring grid with a fixed 6 Å margin.

The complete V2 panel ran with five pockets per case, exhaustiveness 8, and fixed seed 42. It recorded **6/10 passing** and failed the predeclared panel threshold. The top pose recovers 1STP (0.872 Å), 1IEP copy B (0.839 Å), 1HVR (0.515 Å), 1GKC (1.774 Å, explicit Zn), 1OYT (0.321 Å), and 1P62 (0.282 Å). It failed 2F12 (5.232 Å RMSD), 1UYG (22.551 Å and 20.415 Å site offset), and 2H4G (7.204 Å). 1Q4T's best pose was 7.358 Å RMSD, and three of five pocket searches timed out, so its search is incomplete and remains failed. The full machine-readable result is `benchmark/results/docking/multisite-v2-full-scored-20261020/latest.json`; its poses, inputs, and logs are preserved in the adjacent `artifacts.zip`.

The panel's final JSON was written before the runner hit `NameError`s in its summary and exit-code statements after checkpoint refactoring. Both source references are fixed. A one-case full diagnostic panel passed and returned exit code 0 through the corrected summary and exit paths. These runner defects did not change the already-written ten-case results or verdict.

## NCBI live verification

The three previously failing direct NCBI tests were rerun with a 300-second per-search poll budget. All three failed because searches did not complete within that budget. The live log recorded NCBI RTOE=21,223 seconds (about 5.9 hours); the client retained the accepted RID and returned a bounded timeout without resubmitting. The consecutive-run assertion therefore recorded 0/3 successes. Request pacing and RID retention pass their offline regressions, but the provider failures remain unresolved. The exact JUnit evidence is `ncbi-live-rerun.xml`; no local or cached response is substituted for a live NCBI result.

## The 197 audited cases

The previous complete audit retains terminal evidence for all **197** cases: **194 passed, 3 failed, 0 skipped, 0 missing**. These are retained prior results, not a fresh 197-case execution in this repair. The three provider cases also failed in the fresh NCBI rerun. See [the complete audit](../2026-10-19-complete-audit/REPORT.md) and [the provider follow-up](../2026-10-19-provider-docking-followup/REPORT.md).

## Combined repair follow-up — 2026-10-20

After integrating the newer branch repairs, a fresh offline regression run completed with **93 passed, 0 failed, 0 skipped** across `test_ncbi_status_contract.py`, `test_docking_integrity.py`, `test_docking_multisite.py`, `test_blast_resilience.py`, and `test_redock_runner.py`. The JUnit record is `incremental-regressions.xml`. It covers the supported NCBI `GAPCOSTS`, `SHORT_QUERY_ADJUST`, `FORMAT_TYPE`, tool/email fields, process request pacing, retained RIDs, explicit Vina timeout handling, and ligand-aware pocket grid sizing. Source compilation and `git diff --check` also pass.

The V2 protocol is now checked into `benchmark/fixtures/docking/PROTOCOL_V2.md`. Its ligand-aware sizing rule is implemented and unit tested: each receptor-ranked pocket box is expanded to contain the reference ligand's heavy-atom span plus 8 Å, capped at 40 Å; an unrepresentable ligand fails that candidate explicitly. The recorded 6/10 V2 panel predates this sizing change and remains historical evidence for the prior implementation. This workspace does not have Vina, Open Babel, or fpocket executables available, so the full panel was not rerun against the final V2 method. Do not interpret the prior 6/10 as a result for the final method.

A broader test command briefly included `test_blast_comprehensive.py`, which makes live NCBI and EBI calls. It recorded provider failures and was interrupted; it is not counted in the offline regression total. The independently recorded three-case NCBI live rerun remains 0/3 because NCBI advertised a 21,223-second queue estimate beyond the bounded poll budget. No provider pass is claimed.
