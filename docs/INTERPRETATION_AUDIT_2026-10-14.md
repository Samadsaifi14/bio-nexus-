# Interpretation and implementation verification

Baseline inspected: main commit 4d5e94b6722dd51c9efd81cf183248ebae9b7832.

## Confirmed baseline evidence

The current frontend, backend CI, scientific foundation, cross-platform benchmarking, security and deployment workflows passed on that baseline. Those workflows select test subsets. Their success does not establish completion of every capability in the 25-feature competitor roadmap.

The repository's scientific status ledger and verification matrix retain partial/protocol-ready/validation-pending categories. Some ledger entries predate newer changes and require an evidence-backed refresh; they must not be promoted to validated solely because modules exist or a build succeeds.

## Repairs included with this audit

- RNA-seq now has a dedicated deterministic, evidence-linked explanation in the result workspace: contrast direction, normalization, declared thresholds, QC/PCA meaning, heatmap selection, enrichment status and review caveats. It uses emitted values and artifact links, not recalculated statistics or invented biology.
- An empty DEG list, an exploratory heatmap, no significant enrichment and unresolved enrichment estimates have distinct explanations.
- Interpretation SSE processing preserves event boundaries across arbitrary network chunks and UTF-8 byte splits. Cancellation reaches the fetch and reader. Truncated streams and malformed event schemas fail explicitly.
- The legacy UI displays the reported model rather than a hard-coded model name. Accession-like text no longer manufactures NCBI citation links; supplied links must use HTTP(S).
- Legacy streaming AI explanations are buffered per provider attempt and passed through the numeric evidence gate before exposure. Failed partial replies cannot be concatenated with a backup provider's output. The non-streaming path uses the same gate.
- Numeric presence is explicitly not semantic, citation, unit, causal or biological validation. The tool interpreter already applies a numeric gate; its existing resilience tests are now included in backend CI.
- New tests cover fragmented events, Unicode, cancellation, unsafe links, missing values, RNA-seq null outcomes, numeric hallucinations and provider fallback.
- The complete backend audit, previously triggered only on an old audit branch or manually, now runs on relevant main changes and retains a JUnit report. Local-verification builds avoid outbound build telemetry.

## Verification boundaries

The local execution environment was offline during this review. Source inspection and publishing use the connected GitHub application; actual execution of the new checks is delegated to repository CI, not claimed as local execution.

A live provider request, every production tool route, every licensed external engine and paid-tool parity are not established by these deterministic tests. Missing provider configuration or exhausted quota must remain visible as unavailable, with the deterministic RNA-seq explanation still accessible.

Full scientific completion requires the workload-specific benchmark and live integration evidence declared in the roadmap. This document does not mark all 25 competitor capabilities complete.

## Concurrent docking regression identified

While this audit was in progress, commits through 12c7d9dfcaddd4258e55dcf227306b635349bdc8 introduced an APK-based docking-validation prototype into the client page. It inferred pocket geometry from decompiled code patterns, invented interaction counts from keywords and residue classes, and imported child_process/fs into a browser module.

That path is excluded from the molecular result workspace. The exported scientific prototype entry point now fails closed with an explanation; the original structural docking page is retained. The prototype source remains for history, but code inventory cannot be interpreted as protein-ligand geometry, interaction measurements, molecular confidence or redocking validation. Its shell helper also uses argument-vector execution rather than concatenated shell input. The invalid Next.js moduleNameMapper configuration and external prototype alias are removed.

This repair does not establish new docking accuracy or paid-tool parity; those require recorded structure/pose evidence and the declared redocking benchmark.
