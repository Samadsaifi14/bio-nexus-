---
title: Bio Nexus API
emoji: 🧬
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Bio Nexus 🧬

**A bioinformatics pipeline engine that removes the need for expertise to get expert results.**

You paste a sequence and press **Run**. Bio Nexus returns one comprehensive, AI-interpreted page — BLAST hits, annotation, domains, structure, and plain-language explanation — without you touching a single CLI tool or opening a single database tab.

```
NCBI → paste sequence → BLAST → confusing output → copy accession →      (the old way)
open UniProt → new tab → scroll → open AlphaFold → download PDB → ...

Paste sequence → press Run → read one page that explains everything.    (Bio Nexus)
```

## Features

### Sequence & alignment
- **BLAST** — global/local database modes, DNA and protein queries, E-value/bit-score/identity explained inline
- **Pairwise alignment** — global & local (Needleman-Wunsch / Smith-Waterman), standalone tool or "Align pair" from any BLAST hit
- **MSA** — ClustalOmega, MUSCLE, Kalign, MAFFT, T-Coffee with method selector and color-coded viewer
- **Primer design** — Primer3 with configurable product size, Tm, GC content

### Evolution & annotation
- **Phylogenetic tree** — NJ / UPGMA / ML methods, bootstrap colour scale, rectangular/circular layouts, SVG/PNG/Newick export
- **Domain & motif analysis** — InterProScan (Pfam, SMART, PROSITE…) plus raw-sequence PROSITE scanning
- **Pathway enrichment** — Reactome + KEGG with statistical enrichment
- **UniProt / function prediction / protein interactions** — annotation, function inference, interaction lookup

### Structure & drug discovery
- **Structure viewer** — PDB retrieval + AlphaFold prediction, in-browser 3Dmol.js rendering
- **Structure analysis** — Ramachandran plot, secondary-structure assignment, Foldseek structure comparison
- **Molecular docking** — self-hosted AutoDock Vina 1.2.7, full log (RMSD l.b./u.b.), RMSD table, run-config UI
- **MD simulation** — Amber-style implicit solvent, verified force-field × solvent matrix (ff14SB/ff15ipq/ff19SB/amberfb15/CHARMM36 × OBC1/OBC2/GBN2), integrity startup probe
- **ADMET** — RDKit descriptor computation with traffic-light property readout

### Sequencing
- **Sequencing pipeline (MVP)** — FASTQ QC → trimming → assembly/consensus → variant calling → annotation (SARS-CoV-2 reference)

### Platform
- **AI interpretation** — LiteLLM with model fallback chain (Groq → Gemini → Ollama); honest visible banner when an upstream model fails
- **Pipeline wizard** — one 8-step run: BLAST → UniProt → MSA → Phylo → Domains → Pathway → AlphaFold → AI, with progressive reveal
- **Jobs & sharing** — persistent job history, token-based share links, PDF/JSON report export
- **Accounts** — guest → Google account upgrade with zero data migration
- **API keys** — `sk_bio_` scoped keys with `X-API-Key` auth
- **Caching & monitoring** — Redis-backed `@ttl_cache`, `from_cache` flags, `/api/admin/cache-stats`, Sentry
- **Learning** — `/learn` documentation, glossary, inline help popovers, first-run tutorial

## Pipeline architecture

```
User input (sequence / FASTQ / SMILES / PDB ID)
        │
        ▼
Pipeline selector — "What do you have?" → "What do you want to know?"
        │
        ▼
Pipeline engine — task DAG · async workers · Redis · job status polling
        │
        ├── BLAST (EBI)          ├── MSA / Phylo / Domains
        ├── UniProt              ├── Pathway enrichment
        ├── AlphaFold / PDB      ├── Docking / MD / ADMET
        └── Sequencing           └── Function / Interactions
        │
        ▼
Results aggregator — normalises + cross-references every tool output
        │
        ├── Visualisation layer (in-browser, nothing downloads)
        └── AI interpretation (LiteLLM · streaming)
        │
        ▼
Unified result page — one URL · shareable · exportable (PDF/JSON)
```

## Repository layout

```
├── bioai-platform/
│   ├── frontend/          # Next.js + TypeScript + Tailwind (dark-only OLED design system)
│   └── backend/           # FastAPI · async workers · Supabase · Redis · OpenMM · RDKit
├── bio-nexus/phase0/      # Student validation / outreach playbooks
├── MASTER_PLAN.md         # Product master plan (v4.0) — status of every phase
├── BioFlow_AI_PRD.md      # Product requirements (v3.0) — feature specs + roadmap
├── implementationplan.md  # Sprint plan with shipped markers
├── design.md              # Design system reference
├── appflow.md             # Application flow / sitemap
├── schema.md              # Database schema
└── techspec.md            # Technical specification
```

## Stack

- **Frontend** — Next.js (App Router), TypeScript, Tailwind CSS, Phosphor icons, 3Dmol.js
- **Backend** — FastAPI, Uvicorn, async task workers, LiteLLM, Biopython, OpenMM, RDKit, reportlab
- **Data** — Supabase (auth + storage), Redis (cache/queue), external APIs: EMBL-EBI, NCBI, UniProt, RCSB PDB, AlphaFold DB, InterProScan, Reactome, KEGG, PubChem

## Getting started

**Frontend:**
```bash
cd bioai-platform/frontend
npm install
npm run dev          # http://localhost:3000
```

**Backend:**
```bash
cd bioai-platform/backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Environment variables are documented in `techspec.md` (§ Environment Variables). The backend serves `/api/pipeline/v2`, `/api/alignment`, `/api/docking`, `/api/md`, `/api/sequencing`, and the rest under `/api/*` — full list in `bioai-platform/backend/app/main.py`.

## Status

- **v4.0 (2026-08-05)** — full toolset milestone. Phases 1–2 shipped; Phase 3 shipped except homology modeling; Phase 4 partial (docking + ADMET shipped); sequencing MVP shipped. See `MASTER_PLAN.md` §9 for the v4.0 changelog.
