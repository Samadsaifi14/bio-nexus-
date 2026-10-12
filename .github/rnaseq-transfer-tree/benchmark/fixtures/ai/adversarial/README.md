# AI adversarial evidence-integrity fixture

Ground truth source: **hostile-by-construction inputs**, not real data. The
benchmark asserts the Evidence Engine's honesty contract:

1. Fabricated numbers must be **visible and rejected** (see `cases.json`
   `EV-GAP-*`): numeric claims absent from the linked evidence payload →
   `unsupported_numeric_claims` + `rejected: true`.
2. Unverifiable references (accessions/papers not in the session) → rejected.
3. Structurally broken graphs (`EV-STRUCT-*`) must fail the named validation
   check (`graph_reference`, `claim_fields`, `honest_claims`, `source_fields`,
   `graph_nonempty`).

## Tracked semantic gaps (`expectation: gap`)

These are **not passed** — they are recorded as known liabilities that the
structural engine cannot detect, and they require the external semantic
entailment/LLM audit layer before publication-level claims are made:

| Case | Liablity |
|---|---|
| `EV-SEM-001` | Qualitative over-claim (e.g. "p53 controls lifespan") shares vocabulary with sources → mislinked as supported |
| `EV-SEM-002` | Keyword coincidence creates a spurious support edge ("TP53 mutations in airline crew") |
| `EV-SEM-003` | Fabricated *sources* (an NGS "validation" claim about sequencing that never ran) |

Policy: any result exporting claims matching these patterns must carry the
`gap` flag and never be labelled `validated`. The release gate blocks if a gap
case is silently converted to a pass.

Run: `python benchmark/fixtures/ai/adversarial/run_evidence_adversarial.py`
Result: `benchmark/results/ai/adversarial/latest.json`