# Bio Nexus — Definition of Done

**Purpose:** this is why features went missing after being marked ✅. A tool got a one-line spec, someone built the happy path, it got checked off, and the sub-features that were never written down never got built or never got verified. This file is the gate that stops that.

**Rule:** nothing gets a ✅ in `IMPLEMENTATION_LOG.md` or `MASTER_PLAN.md` until it has passed every step below. No exceptions for "it's basically done."

---

## Step 1 — Before writing code: write the manifest

Every analysis tool gets a row in `FEATURE_VERIFICATION_CHECKLIST.md` *before* implementation starts, not after. The manifest answers, in writing:

- What are ALL the outputs a domain expert would expect from this tool? (Not just the one you're excited to build.)
- What does each output look like in the UI — table, chart, downloadable file, inline text?
- What's the error/empty/partial state for each output?
- What's exportable, and in what format?
- Is there a LearnPopover / `/learn` entry for every new term this tool introduces? (per `RULES.md` §10)

If you can't answer these before coding, you don't understand the tool well enough yet — go read one more reference implementation or paper.

## Step 2 — While building: no silent partial features

If a sub-feature in the manifest turns out to be out of scope for this pass, it does NOT get quietly dropped. It gets moved to the manifest's "Deferred" column with a reason. A deferred item is visible; a dropped item is invisible, and invisible is the whole problem we're fixing.

## Step 3 — Before marking ✅: verify live, not from memory

Whoever ships the feature must actually click through the manifest in the running app (not the local dev version off a stale branch) and tick each row. This includes:

- [ ] Every output in the manifest renders with real data
- [ ] Every output has a working loading / error / empty state (per `RULES.md` "Error Display Rule")
- [ ] Every export button actually produces a valid file
- [ ] The tool appears correctly in the pipeline wizard chain if it's meant to (check `pipeline_v2` step list)
- [ ] The tool's job type is in the durable worker's `MAX_CONCURRENT` map if it's long-running (per `durable-worker-design.md` §4.3) — a tool with no concurrency cap is itself a missing feature, not just a scaling risk
- [ ] Share links work for this job type (`share_token`)
- [ ] PDF/JSON export includes this tool's output, not just the tools that existed when the exporter was last touched
- [ ] A `/learn` doc entry exists for any new scientific term this tool surfaces

## Step 4 — Update docs in the same PR

`MASTER_PLAN.md` / `IMPLEMENTATION_LOG.md` get their ✅ updated in the same commit as the code, referencing the manifest row. A doc update that happens later, from memory, in a batch, is how "done" drifts from "actually done."

## Step 5 — Quarterly re-audit

Every existing manifest row gets re-verified against the live app once a quarter (or after any big refactor — e.g. the v4.0 design system rebuild is exactly the kind of change that silently breaks an export button or hides a panel behind a new CSS token). Log the audit date in the manifest. A row that hasn't been re-verified in >90 days is not trustworthy evidence that the feature still works.

---

## Anti-patterns this is specifically banning

- Marking a whole tool ✅ because the core computation works, without checking every declared output renders.
- Writing "X module ✅" in a doc based on remembering you built it, instead of clicking through it that day.
- Adding a new tool to the backend without adding it to the pipeline wizard, the exporter, and the worker's concurrency map in the same pass.
- A one-line spec entry for a tool ("interaction lookup module") standing in for an actual feature manifest.
