# AI prompt-set corpus (deterministic shaping control)

Ground truth source: **deterministic, template-derived contexts** — not live LLM
output. This fixture proves the `protein_analysis` prompt builder contract
without any model call:

- Every context (216 variants across 18 curated slices) builds a prompt with
  **zero un-replaced template placeholders**.
- Live-API text containing `{` or `}` is escaped so the template never crashes
  and never silently falls back (`hazard_braces_*` slices keep the literal
  braces — that is the point).
- Omitted/absent fields degrade to the documented `N/A` markers (honesty),
  never to fabricated values.
- The builder embeds the exact supplied numbers/identifiers; it does not invent
  them.

## Scope / non-claims

This is a **shaping** control. It verifies template stability and honesty of
omission handling. It does **not**:

- judge the biological correctness of any model response;
- exercise a live model, API, or network;
- establish that a model will avoid hallucinating (that is covered by the
  `ai/adversarial` evidence-integrity fixture, which is a different contract).

## Regenerate / verify

```bash
python benchmark/fixtures/ai/prompts/generate_prompt_corpus.py
```

Result: `benchmark/fixtures/ai/prompts/prompt_corpus.json` (schema
`bionexus-ai-prompt-set/v1`). Exit 0 = ≥200 variants produced and every variant
passed the builder contract.