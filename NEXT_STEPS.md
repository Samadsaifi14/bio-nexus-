# Bio Nexus — Next Steps

**Last Updated:** August 2026
**How this file works:** ordered by priority, top to bottom. Don't start item 3 while item 1 is open — the whole point is stopping partial features from accumulating again.

---

## 1. Close the audit gap (do this first, before any new feature work)

Work through `FEATURE_VERIFICATION_CHECKLIST.md` top to bottom, starting with the four 🔴 tools:

1. Protein Interactions
2. Function Prediction
3. Pathway Enrichment
4. Sequencing Annotation

For each: tick every row against the live app. Anything that fails becomes a `fix(...)` commit, not a new feature — you're closing gaps in what was already claimed as shipped, not building anything new. Once a tool's checklist is fully ticked, update its "Last verified" date and only then may `IMPLEMENTATION_LOG.md` claim it as genuinely complete.

Then spot-check the 🟢/🟡 tools in the same file — lower risk, but still unverified against a live app as of this writing.

**Why this order:** every hour spent here prevents a future hour of "wait, why doesn't X work" discovered by a user or by you weeks later. This is strictly higher-leverage than starting Phase 3 depth work on top of an unverified foundation.

## 2. Adopt the process going forward

From this point on, every new tool or module follows `DEFINITION_OF_DONE.md`:
- Manifest written in `FEATURE_VERIFICATION_CHECKLIST.md` *before* coding starts
- Live verification, not memory, before a ✅ lands in the docs
- Docs updated in the same commit as the code

This is the actual fix for "I had to check them one by one" — it moves the checking from an occasional retroactive audit (expensive, easy to skip) to a mandatory gate before anything is called done (cheap, hard to skip because nothing ships without it).

## 3. Resume Phase 3 — sequencing depth

Once Sequencing Annotation passes its audit in step 1, the actual Phase 3 remaining work (per `MASTER_PLAN.md` §5) is:
- RNA-seq differential expression module
- Larger file storage and more compute for bigger FASTQ inputs

Write the manifest for RNA-seq differential expression before writing any code for it — this is the first module built entirely under the new process, so it's worth being disciplined about it as the template case.

## 4. Cross-cutting gaps worth checking regardless of per-tool audit outcome

These came up while reviewing the specs and are worth a direct check rather than waiting to hit them per-tool:

- **Exporter completeness** — does `/api/export/job/{id}` actually include output from every tool that's shipped since the exporter was last touched, or only the tools that existed when it was written? This is a classic silent-gap pattern: the exporter doesn't error when a tool's data is missing, it just omits it.
- **Pipeline wizard step list** — the documented 8-step chain (BLAST→UniProt→MSA→Phylo→Domains→Pathway Enrichment→AlphaFold→AI) doesn't include Docking, MD, ADMET, Function Prediction, or Protein Interactions. Confirm that's an intentional design decision (these are heavier/optional, entered separately) and not an oversight — if intentional, add one sentence to `MASTER_PLAN.md` §4 saying so, since right now a reader has to infer it.
- **Worker concurrency map** — confirm every long-running job type table (`docking_jobs`, `sequencing_jobs`, `jobs`) has full `MAX_CONCURRENT` coverage for every `tool_type` it dispatches, including any tool added after `durable-worker-design.md` was last updated.
- **`/learn` coverage** — spot check whether every scientific term introduced by the 🔴 tools above has a LearnPopover, since those tools are also the least-documented in the specs and likely the least-documented in-app too.

## 5. Phase 4 (not started — do not begin until steps 1–2 are complete)

Lab workspaces, custom pipeline builder, institution licensing, public API access. No manifest work needed yet — just don't start building here while the audit gap from step 1 is open, or you'll be adding new unverified surface area on top of old unverified surface area.

---

*When step 1 is fully closed, delete this file's "Last Updated" caveat above each item as it's resolved, or move completed items into `IMPLEMENTATION_LOG.md` per the normal process.*
