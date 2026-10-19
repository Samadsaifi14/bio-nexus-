# Targeted repairs — 2026-10-19

Code checkpoint: 118 targeted tests passed, zero skips. Original three NCBI tests and the original ten-complex native panel are executing separately; their final results will be retained in the comparison report. This checkpoint does not assert that the remaining scientific/provider failures are resolved.

NCBI submission now uses documented GAPCOSTS, XML2_S and short-query adjustment, includes tool/email identity, and omits undocumented ASYNC and Entrez api_key parameters. Queues exceeding the interactive RTOE threshold retain the accepted RID and explicit incomplete status. Direct NCBI tests retain their biological assertions.

Native Vina accepts an explicitly bounded execution budget (1–1800 seconds; production default unchanged at 300). The original panel is being run with 900 seconds per complex and retains the <8 Å site, top-mode-1 <2 Å RMSD and ≥70% panel gates. Timeout stdout is retained. A longer compute budget is not a changed accuracy threshold.

The revised method is declared in benchmark/fixtures/docking/PROTOCOL_V2.md before its comparative execution. It will have separate results and will not replace the original baseline verdict.
