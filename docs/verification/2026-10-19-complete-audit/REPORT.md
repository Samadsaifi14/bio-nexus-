# Complete-case audit follow-up — 2026-10-19

Follow-up: [provider fixes, CI isolation repair, and native docking outcomes](../2026-10-19-provider-docking-followup/REPORT.md). This dated report retains its original results.

The missing-result gap is closed: **197/197 previously unreported cases now have terminal test outcomes, with zero skips and zero unreported cases**. Outcomes: **194 passed, 3 failed**. A timeout is a recorded failed test, not a successful biological result. **All 20 original skipped cases now pass.**

**The entire request is not scientifically complete. The native docking panel still fails at 4/10**, improved from 3/10 after correcting 1UYG ligand chemistry. Remaining remote-provider failures are listed below. No RMSD cutoff, blind-pocket selection rule, pose order or panel acceptance fraction was relaxed.

## What changed

- The audit collects exact node IDs, writes flushed setup/call/teardown journals, retains terminal cases when a later test crashes, and retries only unreported cases in isolated processes. A case is passed only after a completed passed call and teardown. Backend pytest loads the skip guard by default, including ordinary invocations without the audit wrapper. Missing dependencies and runtime/collection skips fail instead of being silently omitted; a controlled plain-pytest probe verifies this. Infrastructure deadlines and crashes also prevent a green audit, even after recovery. Evidence directories are immutable.
- Native BLAST+, R/DESeq2/tximport and plotting dependencies are provisioned. CI now installs BLAST in the full-suite job, provisions the full official Swiss-Prot snapshot and allows enough time for complete reporting. The MD unavailable-forcefield guard uses a controlled unavailable combination instead of skipping on machines where all forcefields work.
- Fuzz tests use signed test JWTs and actual signature verification. Their controlled HTTP connection failures test validation and outage handling; they do not produce mocked biological outputs. All 71 pass. Live feature/provider tests remain separate and fail explicitly on errors.
- Upstream HTTP failures return sanitized 502 responses. RCSB keyword search uses the documented `full_text` service and handles 204 as no results. Its live insulin test passes. Foldseek respects configured proxies and returns sanitized failures; both live structure comparison cases pass. Interaction tests use the actual serialized score dictionary without changing score/ranking assertions.
- The two pipeline BLAST cases now call the actual production `_run_blast` route instead of copying the direct NCBI client. The multi-sequence assertion requires all five known queries to succeed, with actual provider/count/accessions retained as JUnit properties; previously it accepted just one success. Direct NCBI submission, polling and XML tests remain distinct and fail on provider errors.
- NCBI rejects empty/malformed query strings before submission and does not interpret an unrelated HTML page as ready. These guards have explicit regressions. Remote NCBI roundtrip failures remain failures; the local Swiss-Prot provider is not substituted for a direct NCBI test.
- Invalid deposited ligand bond perception falls back to the official RCSB Chemical Component Dictionary. Exact atom names/elements must match all heavy atoms. The dictionary supplies bonds and charges only; every heavy-atom coordinate comes unchanged from the deposited residue. The source CIF, structures, native poses, version hashes and export failures are retained. fpocket descriptors now read its actual output path.

## Execution coverage

The final collected set and the latest per-node ledger are checked for exact coverage. The ledger contains **1608 unique test results**, with **1605 passes and 3 failures**. This is an aggregate of isolated module runs and targeted post-fix reruns, not a claim that one uninterrupted pytest process passed. Once all non-BLAST IDs had retained outcomes, duplicate remote runs were stopped explicitly; completed phase journals were preserved and only unreported BLAST IDs ran in two isolated recovery workers. Recovery uses the comprehensive suite’s documented 900-second case budget so the application can return its bounded errors instead of being cut off prematurely at 180 seconds. The interruption and snapshot provenance records are retained. The archive retains initial failures and the reruns that superseded them. The three affected original modules are feature validation (102), fuzzing (71), and comprehensive BLAST (24).

`affected-197-cases.json` maps every original missing ID to its latest outcome and evidence. `original-20-skips.json` extracts the exact IDs and original skip reasons from the October 18 JUnit archive and maps all 20 to current passes. `test-evidence.zip` contains phase journals, commands, process results, logs, JUnit, the final collection, attempt history and the complete latest ledger.

R numerical tests ran against real DESeq2 1.42.0 and tximport. Native BLAST+ 2.12.0 searched the complete official Swiss-Prot 2026_03 snapshot (575,748 sequences), recovering **8/8** accession controls through the production route. Queries originate in that snapshot; this establishes accession recovery and routing, not novel-protein annotation accuracy or NCBI availability.

## Native docking result

Vina 1.2.7, fpocket commit `4bb0d8447f62fee77e2c3c29f54b5fcaf5e2c066`, Open Babel 3.1.0 and RDKit 2026.09.1. Exhaustiveness 32, seed 42, mode 1, original receptor-frame RMSD criteria. The panel requires at least 7/10 passes and an essential control.

| Complex | Outcome | Native metric or failure |
|---|---|---|
| 1STP | PASS | 0.856105 Å |
| 1IEP | FAIL | grid does not cover site (offset 59.0 A) |
| 1HVR | PASS | 0.514878 Å |
| 2F12 | FAIL | grid does not cover site (offset 10.1 A) |
| 1GKC | FAIL | grid does not cover site (offset 19.4 A) |
| 1OYT | PASS | 0.320809 Å |
| 1UYG | PASS | 0.656064 Å |
| 2H4G | FAIL | 7.366092 Å |
| 1Q4T | FAIL | grid does not cover site (offset 19.5 A) |
| 1P62 | FAIL | grid does not cover site (offset 9.7 A) |

1UYG is now a measured pass (0.656064 Å) using official PU2 chemistry. Five complexes still fail the predeclared top-pocket location check, and 2H4G misses the 2 Å pose threshold. For 1IEP, the top-ranked pocket is 4.78 Å from the second deposited STI copy on chain B, but the declared extraction selects chain A (59.03 Å away); this panel does not reselect the reference instance after seeing pocket output. The other four location failures remain outside 8 Å of every matching deposited ligand instance. Comparing fpocket cavity-sphere centers with lining-atom centers did not resolve the location failures. Choosing a pocket or pose using the crystal reference would change the benchmark and was not used. The failed Open Babel SDF export for 1OYT remains labeled separately; its native-coordinate metric and restored-graph SDF are retained.

## Remaining failed test cases

- `tests/test_blast_comprehensive.py::TestNCBIBlastIntegration::test_ncbi_blast_full_roundtrip_short_seq`
- `tests/test_blast_comprehensive.py::TestNCBIBlastIntegration::test_ncbi_blast_parse_xml`
- `tests/test_blast_comprehensive.py::TestBlastReliability::test_consecutive_blast_runs`

These are explicit test failures, not missing results or skips. An independent public crambin job remained `WAITING` in a cache-bypassed later poll, well after its 22-second submission estimate; the actual response body, response metadata and evidence-file timing are in `ncbi-wire/` inside the archive. This is evidence about this execution, not a claim that every NCBI request is unavailable. The report does not certify remote service availability, universal blind docking accuracy, or all-roadmap scientific validation.

## Reproduce

```sh
# Install backend requirements, pytest-asyncio/pytest-timeout, BLAST+, and the R packages in CI.
python bioai-platform/backend/scripts/provision_local_blast.py /absolute/reference/swissprot
BIONEXUS_BLAST_DB_ROOT=/absolute/reference/swissprot python scripts/run_feature_audit.py --outdir /absolute/fresh-audit --module-seconds 2400 --case-seconds 900
# With declared fpocket/Open Babel/Vina tools available:
python benchmark/fixtures/docking/run_redock_panel.py --outdir /absolute/fresh-redocking
python benchmark/verify_fixtures.py check
```

The full audit exits nonzero for any failed case, converted skip, incomplete collection, unrecovered execution, process crash or deadline. It cannot guarantee a third-party service will succeed; it guarantees those outcomes cannot silently disappear or be counted as passes.
