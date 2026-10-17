# Verification continuation — 17 October 2026

The complete audit at e31fae5 collected 1,537 tests: 1,456 passed, 53 failed, 28 skipped (run 38583934432). These are historical results, not a test of today's HEAD 26793f2 or this repair.

This repair fixes statistical significance figures: true -log10(p), preserve zero p-values with an explicit 300 cap, omit missing/invalid p-values. Previously the plot multiplied by ten and interpreted zero as one. Statistical validation now rejects empty results and two-group tests with fewer than two observations per group. CSV exports retain group sizes/significance and quote arbitrary test names. Missing statistics remain null, as required by strict JSON.

Regression tests cover plotting values, missingness, CSV quoting, empty-result validation and existing engine behavior. The former insufficient-sample test expected NaN, which is incompatible with strict JSON, and now requires null. Its tiny-sample validation fixture now actually uses fewer than two observations; a two-observation group is mathematically permissible for the declared approximate method.

The workflow runs statistics and interpretation regressions independently so slow external integration tests do not delay their result.

Unresolved audit categories include runtime/reference-version differences, authenticated smoke fixtures, worker claim expectations and live provider timeouts. The public release must not be called fully verified from selected passing checks.

The execution environment remains unavailable; uploaded local lecture/count files could not be read during this continuation. No claim of slide alignment or fresh local/browser testing is made.
