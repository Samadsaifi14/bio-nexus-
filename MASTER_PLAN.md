# Bio Nexus Platform — Master Plan v3.0

> A bioinformatics pipeline engine that removes the need for expertise to get expert results.
> User arrives with a biological question and raw data. Leaves with a complete, interpreted answer — having touched nothing in between.
>
> Solo founder · Indian M.Sc. bioinformatics grad · Product-first

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
├── FASTQ files (Phase 3)
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
       │     E-value · bit score · % identity · coverage
       │
       ├── UniProt (REST lookup)
       │     Function · domains · disease associations · 24h Redis cache
       │
       ├── AlphaFold DB (Phase 1)
       │     3Dmol.js render · in-browser only · no downloads
       │
       ├── Phase 2 modules
       │     MSA · Phylogenetic tree · Pfam domains
       │     KEGG pathways · Primer3 · DiffDock (via Replicate)
       │
       └── Phase 3 modules
             RNA-seq · Variant calling · ChIP-seq
       │
       ▼
Results aggregator        ◄── THE KEY PIECE YOUR CURRENT CODEBASE MISSES
  Merges all tool outputs into structured JSON
  Normalises formats · resolves cross-references (accession→UniProt→PDB)
  Hands complete picture to AI + visualisation simultaneously
       │
       ├── Visualisation layer
       │     MSA viewer · 3D structure · Phylogenetic tree
       │     All in-browser · nothing downloads
       │
       └── AI interpretation (LiteLLM · streaming)
             Plain language report · citation links · confidence indicators
       │
       ▼
Unified result page
  One URL · shareable · exportable (PDF) · explainable to a first-year M.Sc. student
```

---

## 5. Phase Breakdown

### Phase 1 — Prove the pipeline engine works (Months 1–4)

One workflow. Done better than anyone else has done it. No feature creep.

**Workflow**: Protein sequence → BLAST (EBI) → UniProt annotation → AlphaFold structure → AI report

**Output**: A single result page:
- Top BLAST hits with E-value and identity clearly explained
- UniProt entry distilled to what matters (function, disease associations, active sites, organism)
- AlphaFold structure rendered in-browser with 3Dmol.js — nothing downloads
- AI section that ties it all together in plain language a first-year M.Sc. student can read and act on

No one offers this. Galaxy makes you build a workflow manually. EMBL-EBI runs each tool separately. Nobody gives a unified interpreted result.

### Phase 2 — Expand the pipeline library (Months 5–10)

New pipelines:
- **MSA + phylogenetic tree** — paste sequences, get a tree with evolutionary distances explained
- **Domain & motif analysis** — Pfam, PROSITE — what are the functional regions
- **Gene ontology + KEGG enrichment** — given a gene list, what processes are enriched
- **Primer design** — Primer3 integration, conditions included
- **Molecular docking** — DiffDock via Replicate (GPU inference API, not local)

Pipeline selector UI: "What do you have?" → "What do you want to know?" → pipeline recommended automatically

### Phase 3 — Handle raw sequencing data (Months 11–18)

- FASTQ → QC → trimming → alignment → variant calling → annotation → interpreted report
- RNA-seq differential expression
- Larger infrastructure: file storage, longer jobs, more compute
- Significantly expands user base from coursework students to researchers doing published work

### Phase 4 — Platform + collaboration (Months 19–30)

- Lab workspaces (PI + students share a project)
- Custom pipeline builder for advanced users
- Institution licensing
- API access for programmatic use

---

## 6. What Changes Right Now

| Principle | Action |
|-----------|--------|
| Pipeline engine | Build results aggregator that merges BLAST + UniProt + AlphaFold + AI into one output |
| Unified result page | Replace separate BLAST/UniProt tabs with single pipeline results view |
| Student-first | `.edu.in` free tier, ₹299 individual, ₹999 lab |
| Honest AI | Working Groq key installed. Fallback shows visible banner, not fake analysis |
| Outreach | Target M.Sc./PhD/MBBS students. One question: "Walk me through the last sequence you tried to analyze" |
| Architecture | Aggregator layer normalises cross-tool output. AI sees the complete picture, not just one tool's output |

---

## 7. Weekly Rhythm

```
Mon–Thu    Build (pipeline engine, aggregator, one module at a time)
Fri        2–3 user calls (students, not faculty)
Sat        Feedback → incorporate → build-in-public post
Sun        Plan next week — no coding
```

**Hard rule**: Two weeks without a user call → stop building, make calls.

---

## 8. The Honest Challenges

1. **Working AI key** — Groq is installed and tested. If API calls fail, the user sees a visible yellow banner, not fake analysis.
2. **Real user conversations** — Before Phase 2, need 10 conversations with students who tried to analyze a sequence. Ask: "What did you open, what went wrong, how long did it take?"
3. **GPU budgeting** — DiffDock requires a paid inference API (Replicate). Student tier won't include it. Lab tier ($999/mo) covers the cost.
4. **Galaxy comparison** — Deep answer: Galaxy gives power users flexibility. Bio Nexus gives non-experts answers. The markets barely overlap.

---

*Bio Nexus Platform — Master Plan v3.0*
*Pipeline engine · Student-first · India-built*
