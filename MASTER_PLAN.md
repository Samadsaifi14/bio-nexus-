# Bio Nexus — Master Plan

**Version:** 4.1
**Last Updated:** August 2026

> A bioinformatics pipeline engine that removes the need for expertise to get expert results.
> User arrives with a biological question and raw data. Leaves with a complete, interpreted answer — having touched nothing in between.
>
> Solo founder · Indian M.Sc. bioinformatics grad · Product-first

**Current status:** Every core module through Phase 3 is shipped and running through the pipeline engine — see [`IMPLEMENTATION_LOG.md`](./IMPLEMENTATION_LOG.md) for the full sprint-by-sprint build history and what's live as of today. This document covers *why* the product exists and *how* it's architected — it does not track sprint status.

---

## 1. What the Product Actually Is

Not a tool aggregator. Not a BLAST wrapper with AI on top.

The current experience:

```
NCBI → paste sequence → BLAST → confusing output → copy accession →
open UniProt → new tab → scroll entry → open AlphaFold → new tab →
download PDB → open PyMOL → read 3 papers → give up or ask a senior
```

Bio Nexus:

```
Paste sequence → press Run → read one comprehensive page that explains everything
```

This is a **pipeline engine**. Every tool output flows into a results aggregator that normalizes, cross-references, and passes the complete picture to both the visualization layer and the AI interpretation layer simultaneously. The AI doesn't just see BLAST output — it sees what the sequence is, what homologs exist with statistical confidence, what the function annotation says, and what the structure looks like.

**New bioinformatics tools become new modules. The architecture never changes — only the pipeline library grows.**

---

## 2. Target User

**NOT** IIT computational biology faculty (they already have workflows).

The real users:
- **M.Sc. bioinformatics student at JMI or central university** — learning but doesn't know the toolchain
- **PhD student in biochemistry** — suddenly needs to analyze a protein sequence, uncomfortable with CLI
- **MBBS researcher at AIIMS** — found an interesting variant, doesn't know what to do
- **M.Sc. biotechnology final-year project student** — needs results, not tool expertise

These people exist in enormous numbers. They have severe unmet need. You can reach them directly because you **are** one of them.

Pricing reflects this reality:

| Tier | Price | Verification | Users |
|------|-------|--------------|-------|
| Student | ₹0 | `.edu.in` email | Current students |
| Individual | ₹299/mo | — | Early-career researchers |
| Lab | ₹999/mo (3–5 seats) | — | Small research groups |
| Institution | Custom | — | University-wide license |

The free student tier is not a loss — it's the growth strategy. Students graduate, become postdocs, become faculty, become the people who approve institutional licenses.

---

## 3. Competitive Moat

Galaxy Project: free, open-source, 15 years old, hundreds of tools, trusted by reviewers.

You cannot beat Galaxy on **breadth** or **reputation**.

You beat them on:

1. **AI interpretation** — Galaxy has none. Results come back raw. Bio Nexus explains everything in plain language.
2. **Zero setup** — Galaxy requires an account, a server, or an institutional deployment. Bio Nexus requires a Google login.
3. **Plain language output** — designed explicitly for people who aren't bioinformatics experts. This is the real differentiation.

---

## 4. Architecture

```
User input
├── Sequence (FASTA)
├── Gene list
├── FASTQ files
└── Structure (PDB ID)
       │
       ▼
Pipeline selector
  "What do you have?" → "What do you want to know?" → pipeline chosen
       │
       ▼
Pipeline engine
  Task DAG · async workers · Redis queue · Supabase Realtime progress
       │
       ├── BLAST (EBI REST API: nr, swissprot, pdb)
       ├── UniProt (REST lookup, 24h Redis cache)
       ├── AlphaFold DB (3Dmol.js render, in-browser only, no downloads)
       ├── MSA · Phylogenetic tree · Pfam domains
       ├── KEGG/Reactome pathways · Primer3
       ├── Docking (AutoDock Vina) · MD simulation · ADMET
       ├── Function prediction · protein interactions
       └── Sequencing (FASTQ QC → variant calling)
       │
       ▼
Results aggregator        ◄── THE KEY PIECE A TOOL AGGREGATOR WOULD MISS
  Merges all tool outputs into structured JSON
  Normalises formats · resolves cross-references (accession→UniProt→PDB)
  Hands complete picture to AI + visualisation simultaneously
       │
       ├── Visualisation layer
       │     MSA viewer · 3D structure · Phylogenetic tree
       │     All in-browser · nothing downloads
       │
       └── AI interpretation (Groq → Gemini → Ollama fallback, streaming)
             Plain language report · confidence indicators
       │
       ▼
Unified result page
  One URL · shareable · exportable (PDF) · explainable to a first-year M.Sc. student
```

---

## 5. Roadmap Phases

Full build history and what's shipped in each phase lives in `IMPLEMENTATION_LOG.md`. This is the phase *definition* only:

| Phase | Scope | Status |
|---|---|---|
| 1 | Prove the pipeline engine: sequence → BLAST → UniProt → AlphaFold → AI report | ✅ Shipped |
| 2 | Expand the pipeline library: MSA/phylo, domains, pathways, primers, structure, docking, MD, ADMET, function prediction, sequencing MVP | ✅ Shipped |
| 2.5 | Platform hardening: docs, onboarding, monitoring, caching, design system | ✅ Shipped (ongoing) |
| 3 | Handle raw sequencing data at scale: RNA-seq differential expression, larger storage/compute | 🚧 In progress (MVP shipped, depth remaining) |
| 4 | Platform + collaboration: lab workspaces, custom pipeline builder, institution licensing, public API | 🔜 Not started |

---

## 6. Current Priorities

| Principle | Action |
|-----------|--------|
| Real user conversations | Two weeks without a user call → stop building, make calls |
| Student-first | `.edu.in` free tier, ₹299 individual, ₹999 lab |
| Honest AI | Fallback chain shows a visible banner on failure, never fake analysis |
| Outreach | Target M.Sc./PhD/MBBS students directly — "walk me through the last sequence you tried to analyze" |
| Architecture discipline | New tools become new pipeline modules; the aggregator/AI/viz layers never get bolted-on special cases |

### NGS evidence transparency acceptance criteria (September 2026)

- Results name the scientific operation, not a crowded list of possible tools.
- Every stage reports whether its output was directly measured, internally computed, inferred, or produced by a surrogate method.
- A tool/version is reported only when that implementation actually executed; candidate or compatible tools are never shown as executed.
- Synthetic demonstrations are permanently labelled and cannot support biological or accuracy claims.
- Accuracy is reported only after comparison with a recognized truth set in its benchmark regions, with precision, recall and F1 split by variant class.
- GIAB/GA4GH, precisionFDA and SEQC are registered as external comparison sources; an unexecuted comparison displays `NOT_EVALUATED`, never a fabricated score.
- “Same or better” is permitted only when an executed, reproducible benchmark supports the claim for the same sample, reference build, confident regions and metric.

---

## 7. Weekly Rhythm

```
Mon–Thu    Build (one module or hardening item at a time)
Fri        2–3 user calls (students, not faculty)
Sat        Feedback → incorporate → build-in-public post
Sun        Plan next week — no coding
```

---

## 8. The Honest Challenges

1. **Working AI key** — Groq is installed and tested. If API calls fail, the user sees a visible yellow banner, not fake analysis.
2. **Real user conversations** — need a steady cadence of conversations with students who tried to analyze a sequence: "What did you open, what went wrong, how long did it take?"
3. **GPU budgeting** — deep-learning docking (e.g. DiffDock) requires a paid inference API. Student tier won't include it; Lab tier covers the cost if/when added.
4. **Galaxy comparison** — Galaxy gives power users flexibility. Bio Nexus gives non-experts answers. The markets barely overlap.

---

*Bio Nexus Master Plan*
*Pipeline engine · Student-first · India-built*
