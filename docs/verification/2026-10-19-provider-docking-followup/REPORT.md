# Provider and docking follow-up — 2026-10-19

The work is **not fully passing**. The original 197 previously unreported cases retain complete terminal results: **194 passed, 3 failed, zero skipped, zero missing**. The three direct NCBI cases completed a rerun after the XML2/polling changes, before adding outage-body retries; their exact results are in `summary.json` and the retained JUnit report. Earlier outcomes for the other 194 cases are inherited from the [complete audit](../2026-10-19-complete-audit/REPORT.md), not represented as fresh executions.

## Fixes and verification

- Fix remote-provider contract isolation when a real local database is configured: clear both the environment variable and the cached settings value. The preceding full CI run recorded all 1,608 cases (1,602 pass, six fail, zero skip/missing); three failures were this fixture-isolation defect and three were direct NCBI cases. The targeted regressions below were rerun with the full native database configured to exercise the CI condition. Its original six-failure evidence is retained as `ci-bf31-failures.json` in the test archive.
- Request the documented single-file `XML2_S` response and parse both legacy XML and namespaced XML2. Real BLAST+ 2.12.0 outputs for the same full Swiss-Prot query produce identical parsed hits, scores, alignments and metadata. These fixtures are native local outputs, **not live NCBI captures**.
- Poll each RID no more than once per minute, include HTTP time in its wall-clock budget, and cancel requests at the remaining deadline. An API key does not shorten the per-RID interval. A queued search retains its entire budget rather than being declared stuck halfway through.
- Reuse a completed XML poll response rather than immediately downloading it again. A queue timeout returns its accepted RID and never resubmits the same queued query. Cross-worker aggregate request coordination remains the caller's responsibility.
- Retry the observed HTTP 200 `Temporarily unavailable` body with bounded backoff and return an explicit provider-outage error if it persists. This preserves the actual HTTP response status; no result or status code is fabricated.
- Reject unrelated XML/HTML and empty XML2 envelopes instead of interpreting them as completed zero-hit searches.
- Execute native docking after a failed site-coverage check to retain poses and RMSD for diagnosis. **The existing <8 Å site gate, top-mode-1 RMSD <2 Å criterion, and panel ≥70% criterion remain unchanged.** A regression test replays retained native output to prove that a recovered pose cannot override a failed site gate; replay is not counted as a fresh scientific result.
- **71 targeted regressions passed; zero skips. All 20 originally skipped cases were rerun and passed; zero skips.** The preexisting default backend policy still converts collection/runtime skips into failures. The final source collects **1,622 cases** after adding these regressions. A complete backend-suite execution on this final source is not claimed for this follow-up.

## Fresh native docking results

**4/10 passed.** 9/10 cases have retained native predicted poses and measured RMSD. A native execution/preparation error, if listed, remains an explicit failure.

| Complex | Site offset (Å) | Top-mode RMSD (Å) | Verdict | Failure detail |
|---|---:|---:|---|---|
| 1STP | 1.32 | 0.856 | PASS |  |
| 1IEP | 59.03 | 62.015 | FAIL | grid does not cover site (offset 59.0 A); native docking completed for diagnosis |
| 1HVR | 0.49 | 0.515 | PASS |  |
| 2F12 | 10.12 | 3.251 | FAIL | grid does not cover site (offset 10.1 A); native docking completed for diagnosis |
| 1GKC | 19.38 | 19.948 | FAIL | grid does not cover site (offset 19.4 A); native docking completed for diagnosis |
| 1OYT | 2.42 | 0.321 | PASS |  |
| 1UYG | 4.14 | 0.656 | PASS |  |
| 2H4G | 1.37 | 7.366 | FAIL | Top-ranked pose exceeds 2 Å |
| 1Q4T | 19.53 | unavailable | FAIL | Vina exceeded its 300-second execution limit |
| 1P62 | 9.69 | 13.187 | FAIL | grid does not cover site (offset 9.7 A); native docking completed for diagnosis |

The raw source structures, reference chemistry, prepared inputs, native Vina output, logs, exported poses and per-file hashes are retained in `native-docking-artifacts.zip`; `docking-panel.json` records binary and source fingerprints. An RMSD value is not an affinity-validation result.

## Distinct remaining docking causes

The independently computed diagnostic for **1IEP** finds that the native top pose matches deposited ligand copy B at **0.847 Å**, whereas the declared first-instance reference is copy A (**62.015 Å**). The reference-instance policy has not been changed after observing these results. This diagnostic is not an additional panel pass.

For **2H4G**, mode 2 is **1.718 Å** from the crystal while the required mode 1 is **7.366 Å**. Vina generated a near-native pose but ranked another pose first. Selecting mode 2 using crystal RMSD would change the validation rule, so this remains a failed top-pose recovery.

The remaining site-selection failures require an independently validated pocket-selection improvement. A different pocket chosen using the crystal reference would not demonstrate prospective docking performance.

## NCBI evidence and remaining limitation

The older XML2 diagnostic with 10–25 second polling was interrupted after checking the provider's usage requirements. Its partial logs are retained and explicitly excluded from replacement case outcomes. A direct wire diagnostic received HTTP 200 with the exact body `Temporarily unavailable` and no RID; both body and metadata are retained. The earlier completed compliant run is retained separately from the final rerun after adding outage-body retries. The three completed cases use the XML2/polling corrections and preserve the original biological success assertions. The subsequent run with HTTP-200 outage retries was interrupted by a network approval cancellation after the console recorded two failures and the third case started. Its incomplete attempt does not replace earlier terminal results. Outage-body retry behavior is verified by controlled transport regressions; completed live verification on that final revision is pending CI. Provider failures remain failures; no local result is substituted into a direct NCBI test.

Official references: [supported Common URL API formats](https://blast.ncbi.nlm.nih.gov/doc/blast-help/urlapi.html) and [NCBI usage guidelines](https://blast.ncbi.nlm.nih.gov/doc/blast-help/developerinfo.html). Runtime bounds prevent an unavailable external queue from hanging the audit; they cannot guarantee that NCBI completes a search.

## Evidence

- `summary.json`: current focused-test counts and all three fresh NCBI outcomes.
- `affected-197-cases.json`: all original case IDs with terminal results and their evidence locations; inherited evidence resolves against the preceding complete audit.
- `test-evidence.zip`: fresh JUnit files and logs, interrupted diagnostic label, native diagnostic calculations and the late response from the earlier RID.
- `native-docking-artifacts.zip` and `docking-panel.json`: native execution evidence and unchanged scientific verdicts.
- `source-provenance.json` and `SHA256SUMS.json`: source and retained-file fingerprints.
