# BioFlow AI — Product Requirements Document

**Version:** 2.0  
**Author:** Samad (Founder)  
**Date:** June 2026  
**Status:** Phase 2 Complete — Hardening In Progress  

---

## Table of Contents

1. Executive Summary
2. Problem Statement & Founder Motivation
3. Vision & Mission
4. Target Users & Personas
5. Goals & Success Metrics
6. Competitive Landscape & Differentiation
7. High-Level Product Architecture
8. Technical Stack
9. External API & Tool Integration Map
10. Feature Specifications by Phase
11. Guided Wizard System Design
12. Results Page System
13. AI Interpretation Layer
14. Onboarding & Learning System
15. Data Flow & Job Architecture
16. Non-Functional Requirements
17. Risk Register
18. Milestone Roadmap
19. Open Questions & Future Scope

---

## 1. Executive Summary

BioFlow AI is a web-based bioinformatics automation platform that unifies the fragmented ecosystem of biological databases and computational tools into a single, guided, accessible interface. Users describe what they want to accomplish in plain language; the platform handles all database queries, file format conversions, tool executions, and result interpretation automatically.

The platform is designed to serve bioinformatics students and researchers who currently lose hours navigating NCBI, PDB, EMBL-EBI, UniProt, KEGG, and dozens of other resources — downloading files, converting formats, uploading to another tool, and struggling to interpret raw output without expert guidance.

BioFlow AI's core differentiator is not just automation — it is **pedagogical automation**: every result is explained, every parameter is annotated, and every output is rendered visually so that a second-year undergraduate can understand what a BLAST E-value, an RMSD score, or a binding energy actually means for their biological question.

---

## 2. Problem Statement & Founder Motivation

### The Pain

A bioinformatics student who wants to find structurally similar proteins to a given sequence today must:

1. Go to NCBI, search by name or accession, download FASTA
2. Go to EMBL-EBI BLAST, upload FASTA, choose database, wait 5–15 minutes
3. Download BLAST results, manually shortlist hits
4. Go to ClustalOmega, upload sequences, run MSA
5. Download MSA output, go to MEGA or PHYLIP for phylogenetic tree
6. Go to PDB, search for structure, download PDB file
7. Open PyMOL or Chimera locally, visualize structure
8. Separately search KEGG or Reactome for pathway context
9. Try to piece together what all of this means biologically

This is 9+ manual steps across 6+ separate websites, involving file downloads and uploads at every transition, often requiring expert knowledge to interpret intermediate outputs. A student without prior guidance will frequently make mistakes at every step — wrong database, wrong BLAST program variant, wrong alignment parameters — and receive results they cannot interpret.

### The Founder's Experience

This platform was conceived from direct experience failing bioinformatics practical exams not due to lack of knowledge, but due to the overwhelming complexity of navigating these tools and interpreting their raw outputs without real-time guidance. The pain is authentic, the user is known, and the gap is real.

### The Gap No One Has Filled

- **Galaxy Project** solves automation but requires the user to know which tools to chain. It is a tool for researchers, not students.
- **EMBL-EBI Tools** are excellent but siloed — each tool is its own page, results don't carry forward.
- **Nextflow / Snakemake** are for computational biologists writing pipeline code.
- **No existing platform** combines: guided intent capture + automated multi-tool orchestration + visual results + educational interpretation in a single unified interface.

---

## 3. Vision & Mission

**Vision:** A world where any biology student, wet lab researcher, or medical scientist can perform rigorous bioinformatics analysis without needing to be a computational expert.

**Mission:** Automate the entire operational layer of bioinformatics — database access, file handling, tool execution, format conversion — so that scientists can focus on the biology, not the infrastructure.

**Product Tagline (working):** *"Tell us your question. We'll handle the biology."*

---

## 4. Target Users & Personas

### Primary — Bioinformatics Students (MVP Focus)

**Persona: Priya, M.Sc. Bioinformatics, Year 1**

- Enrolled in a university bioinformatics program
- Has theoretical knowledge of BLAST, MSA, homology modeling
- Struggles with the practical execution — which database? which parameters? what does this output mean?
- Needs to complete lab practicals and submit reports
- Pain: spends 3–4 hours on a practical that should take 30 minutes, mostly fighting tool interfaces
- Goal: get correct, explainable results fast so she can understand the biology and write her report

### Secondary — Wet Lab Biologists

**Persona: Dr. Arjun, PhD in Molecular Biology, Postdoc**

- Generates experimental data (protein sequences, gene expression data)
- Knows the biology deeply, does not know the computational tools
- Currently emails a bioinformatics colleague for help or outsources analysis
- Needs reliable, reproducible analysis with results he can trust and present
- Goal: independent bioinformatics analysis without a learning curve

### Tertiary — Independent Researchers / Educators (Later)

- Faculty who want to use the platform for teaching
- Researchers in resource-limited institutions without bioinformatics support
- Science communicators and science journalists doing background research

### Out of Scope (V1)

- Clinical genomics (patient data, HIPAA/DPDP regulated)
- Large-scale genomics pipelines (WGS, RNA-seq at scale)
- Pharmaceutical industry users (commercial KEGG licensing required)

---

## 5. Goals & Success Metrics

### Product Goals

| Goal | Metric | Target (6 months post-launch) |
|---|---|---|
| Reduce time to complete a standard bioinformatics practical | Average session duration for a BLAST→MSA workflow | Under 15 minutes (vs current 60–90 min) |
| Make results understandable without expert | User comprehension score (post-session survey) | 80%+ of users say they understood the results |
| Adoption by students | Registered users | 1,000 students from Indian universities |
| Retention | 30-day return rate | 40%+ |
| Reliability | Successful job completion rate | 95%+ (excluding upstream API failures) |
| Educational value | Users who learned something new (survey) | 70%+ |

### Technical Goals

- Average time from user query to first result display: under 30 seconds for cached results, under 5 minutes for live BLAST
- Zero data loss for user job history
- Platform availability: 99.5% uptime

---

## 6. Competitive Landscape & Differentiation

| Platform | Strengths | Why It Fails Students |
|---|---|---|
| Galaxy Project | 10,000+ tools, reproducible | Requires user to know which tools to use; zero guidance |
| EMBL-EBI Tools | High quality, free | Each tool is a separate page; no continuity between steps |
| Nextflow / nf-core | Production-grade pipelines | Requires coding; for computational biologists only |
| NCBI directly | Authoritative data | No pipeline logic; raw interfaces; no interpretation |
| Benchling | Good UI | Commercial, biology lab focus, not bioinformatics tools |

### BioFlow AI's Differentiators

1. **Intent-first interface.** Users describe their biological question; the platform determines the correct tool chain. No prior knowledge of which tool to use required.

2. **Zero file handling.** The platform never asks users to download or upload sequence files. All data transfer between tools is handled server-side.

3. **Pedagogical results.** Every result is annotated with plain-language explanations. E-values are explained in context. RMSD scores are interpreted relative to the query. Users learn while they analyze.

4. **Curriculum-aligned.** V1 feature set is explicitly aligned with the standard M.Sc. Bioinformatics curriculum (JMI/DU equivalent), meaning students can use it directly for coursework.

5. **Guided wizard.** Step-by-step interface with contextual instructions at each step — the platform teaches as it works.

---

## 7. High-Level Product Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER LAYER                               │
│   Next.js Frontend — Guided Wizard + Results Dashboard          │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    ORCHESTRATION LAYER                          │
│   FastAPI Backend — Intent Parser + Pipeline Executor           │
│   • Workflow Router (maps intent → tool chain)                  │
│   • Job Queue Manager (Redis + Celery/BullMQ)                   │
│   • Result Cache (Upstash Redis, TTL-based)                     │
└──────────┬──────────────────────┬───────────────────────────────┘
           │                      │
┌──────────▼──────────┐  ┌────────▼────────────────────────────┐
│   DATA LAYER        │  │         TOOL EXECUTION LAYER        │
│   Supabase (PG)     │  │   External API Wrappers:            │
│   • Users           │  │   • NCBI Entrez (sequences/BLAST)   │
│   • Job history     │  │   • EMBL-EBI (alignment/MSA)        │
│   • Cached results  │  │   • PDB REST (structures)           │
│   • Saved analyses  │  │   • AlphaFold EBI (prediction)      │
│                     │  │   • UniProt REST (annotation)       │
└─────────────────────┘  │   • STRING-DB (interactions)        │
                         │   • Reactome REST (pathways) [PRI]  │
                         │   • WikiPathways (pathways) [SEC]   │
                         │   • KEGG REST (pathways) [ACAD]     │
                         │   • SwissADME (ADMET properties)    │
                         │   • PubChem REST (compounds)        │
                         │   • ChEMBL REST (drug data)         │
                         └────────────┬────────────────────────┘
                                      │
                         ┌────────────▼────────────────────────┐
                         │        AI INTERPRETATION LAYER      │
                         │   Groq (llama-3.1) — fast explain   │
                         │   Claude API — deep report gen      │
                         └─────────────────────────────────────┘
```

---

## 8. Technical Stack

### Frontend

| Technology | Purpose |
|---|---|
| Next.js 14 (App Router) | Core framework, SSR, routing |
| TypeScript | Type safety throughout |
| Tailwind CSS | Utility-first styling |
| NGL.js / Mol* | 3D protein structure visualization (in-browser) |
| msa.js / custom | Multiple sequence alignment viewer |
| phylotree.js + D3.js | Phylogenetic tree visualization |
| React Query (TanStack) | Server state, polling for async jobs |
| Framer Motion | Wizard transitions and loading states |
| Recharts | Charts (similarity scores, conservation plots) |

### Backend

| Technology | Purpose |
|---|---|
| FastAPI (Python 3.11+) | REST API, async job orchestration |
| BioPython | Sequence parsing, NCBI Entrez, format conversion |
| Celery + Redis | Async job queue for long-running operations |
| httpx | Async HTTP client for external API calls |
| Pydantic v2 | Request/response validation |

### Infrastructure

| Technology | Purpose |
|---|---|
| Supabase (PostgreSQL) | Primary database + auth |
| Upstash Redis | Job queue + result caching |
| Vercel | Frontend deployment |
| Hugging Face Spaces | FastAPI backend deployment (cpu-basic, Docker) |
| Cloudflare R2 | Temporary file storage (PDB files, alignment outputs) |
| Hugging Face Hub CLI | Backend deployment (`hf upload --type space`) |
| Sentry | Error monitoring (frontend + backend) |

### AI & Interpretation

| Technology | Purpose |
|---|---|
| Groq API (llama-3.1-8b-instant) | Fast inline result annotation |
| Anthropic Claude API | Full report generation, complex interpretation |

---

## 9. External API & Tool Integration Map

### Sequence & Database APIs

| Database | API Endpoint | Used For | Rate Limit | Free? |
|---|---|---|---|---|
| NCBI Entrez | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` | Sequence retrieval (GenBank, RefSeq, PDB IDs) | 3 req/s (10 with API key) | Yes |
| NCBI BLAST | `https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi` | Sequence similarity search | Async, ~5–15 min | Yes |
| UniProt REST | `https://rest.uniprot.org/` | Protein annotation, function, GO terms | 200 req/s | Yes |
| EMBL-EBI BLAST | `https://www.ebi.ac.uk/Tools/services/rest/ncbiblast/` | Faster BLAST alternative | Job-based | Yes |
| EMBL-EBI ClustalOmega | `https://www.ebi.ac.uk/Tools/services/rest/clustalo/` | Multiple sequence alignment | Job-based | Yes |
| EMBL-EBI MUSCLE | `https://www.ebi.ac.uk/Tools/services/rest/muscle/` | MSA alternative | Job-based | Yes |

### Structure APIs

| Service | API Endpoint | Used For | Free? |
|---|---|---|---|
| RCSB PDB REST | `https://data.rcsb.org/rest/v1/` | Structure retrieval, metadata | Yes |
| RCSB PDB Search | `https://search.rcsb.org/rcsbsearch/v2/query` | Structure search | Yes |
| AlphaFold EBI | `https://alphafold.ebi.ac.uk/api/` | Ab initio structure prediction | Yes |
| PDBeFold (EMBL-EBI) | `https://www.ebi.ac.uk/msd-srv/ssm/` | Structural alignment | Yes |
| DSSP via BioPython | Local BioPython DSSP wrapper | Secondary structure assignment | Yes |
| PSIPred API | `http://bioinf.cs.ucl.ac.uk/psipred/api/` | Secondary structure prediction | Yes |

### Pathway APIs

| Service | Priority | API Endpoint | Notes |
|---|---|---|---|
| Reactome REST | **Primary** | `https://reactome.org/ContentService/` | Fully free, open-source, high quality |
| WikiPathways | **Secondary** | `https://webservice.wikipathways.org/` | Community-curated, fully open |
| KEGG REST | **Academic fallback** | `https://rest.kegg.jp/` | Free for non-commercial academic use only; do NOT use if platform monetizes |

**Pathway Fallback Logic:**

```
User requests pathway analysis
    ↓
Query Reactome API → found? → return Reactome result
    ↓ not found
Query WikiPathways API → found? → return WikiPathways result
    ↓ not found
Query KEGG REST (academic) → found? → return with attribution note
    ↓ not found
Return: "Pathway not yet annotated in public databases" + suggest manual search
```

### Drug Discovery APIs

| Service | API | Used For | Free? |
|---|---|---|---|
| PubChem REST | `https://pubchem.ncbi.nlm.nih.gov/rest/pug/` | Compound data, structure | Yes |
| ChEMBL REST | `https://www.ebi.ac.uk/chembl/api/` | Drug-target data, bioactivity | Yes |
| SwissADME | `http://www.swissadme.ch/` | ADMET property prediction | Yes (no public API; use web scraping or form submission) |
| SwissDock | `http://www.swissdock.ch/` | Protein-ligand docking | Yes (job-based) |
| STRING-DB | `https://string-db.org/api/` | Protein interaction networks | Yes |

**Note on Docking:** AutoDock Vina has no public API. For V1 docking support, use SwissDock (web job submission) or DockThor web service. Full AutoDock Vina integration requires server-side execution on a compute instance — defer to Phase 4 with budget planning.

---

## 10. Feature Specifications by Phase

---

### Phase 1 — Foundation: Database Access & Sequence Operations (Months 1–3)

**Goal:** Ship a working product that handles the most common student workflow — retrieve a sequence and run BLAST — end to end, with guided wizard and explained results.

#### F1.1 — Intent Capture & Workflow Router

- User lands on the platform and sees: "What do you want to do today?" with suggested starting points
- Guided wizard categorizes intent into one of: sequence analysis / structure analysis / pathway analysis / drug discovery
- Within each category, wizard walks through required inputs step by step
- At each step: what is this field? why do we need it? example values shown

#### F1.2 — Sequence Retrieval Engine

- Input: accession number (NP_, NM_, P12345, etc.), protein/gene name, or raw sequence
- Platform queries NCBI Entrez or UniProt to retrieve the sequence
- Auto-detects sequence type: DNA, RNA, protein
- Displays sequence with annotations (length, organism, description, database source)
- **No file download required by user.** Sequence is held server-side for downstream operations.
- Supported formats returned internally: FASTA, GenBank, raw sequence

#### F1.3 — BLAST Search

- Inputs: sequence (from F1.2 or pasted by user), database selection (guided), BLAST program (auto-selected based on sequence type)
- BLAST program auto-selection logic:
  - Protein query → NCBI or PDB → blastp
  - Nucleotide query → NCBI nr → blastx or blastn (wizard asks: do you want protein products?)
  - User never sees program names unless they choose "Advanced mode"
- Async job submission via EMBL-EBI BLAST API (faster than NCBI for students)
- Real-time progress polling with status updates shown in UI
- Results: hit table with E-value, identity %, alignment length, organism, accession
- Result caching: same sequence + same database = cached for 24 hours

#### F1.4 — Pairwise Sequence Alignment

- Inputs: two sequences (manual paste, accession lookup, or from BLAST hit selection)
- Algorithm selection (guided):
  - "Find shared regions" → Smith-Waterman (local alignment)
  - "Compare full sequences" → Needleman-Wunsch (global alignment)
  - Users never need to know algorithm names; wizard asks purpose instead
- Scoring matrix: auto-selected (BLOSUM62 for protein, match/mismatch for nucleotide)
- Results: alignment visualization with highlighted matches, mismatches, gaps
- Score, identity %, similarity % displayed with explanations

#### F1.5 — File Format Converter

- Inputs: user can paste or upload any of: FASTA, GenBank, FASTQ, raw sequence, PDB
- Auto-detects format
- Converts to any target format on request
- This is a supporting utility, always available regardless of wizard path

#### F1.6 — Basic Results Page (Phase 1 version)

- BLAST results rendered as interactive table
- Click any hit → expand alignment view inline
- E-value, bit score, identity explained inline with tooltips
- AI-generated paragraph: "What do these results tell you biologically?" (Groq API)
- Download options: results as CSV, alignment as FASTA, full report as PDF (basic)

---

### Phase 2 — Alignment, Phylogenetics & Platform Features (Months 4–8) ✅

**Goal:** Add MSA, phylogenetic analysis, domain analysis, pathway enrichment, primer design, and platform features (API keys, share links, export, guest→account upgrade, documentation, monitoring, caching).

#### F2.1 — Multiple Sequence Alignment (MSA) ✅

- Inputs: multiple sequences (from BLAST shortlist, accession list, or paste)
- Algorithm options (wizard-guided): ClustalOmega (default), MUSCLE (alternative)
- EMBL-EBI ClustalOmega API for execution
- Results visualization: color-coded MSA viewer with conservation scores
- Highlight: conserved regions, variable regions, gaps
- Downloadable in: FASTA, Clustal, PHYLIP format (all generated automatically)
- **Status: Shipped**

#### F2.2 — Phylogenetic Tree Construction ✅

- Inputs: MSA output (auto-piped from F2.1, or user-uploaded alignment)
- Method selection: Neighbor-Joining (Clustal Omega guide tree), UPGMA (pure Python p-distance), Maximum Likelihood (local PhyML binary)
- Bootstrap support values (0–1000) with colour scale on tree branches
- Results: interactive phylogenetic tree rendered in browser (PhyloTreeViewer)
  - Rectangular / circular layout toggle
  - Bootstrap colour scale: ≥90 cyan, ≥70 lime, ≥50 orange, <50 red
  - Export SVG, PNG, Newick
- PhyML binary downloaded pre-compiled from bioconda (2 MB, no compilation needed)
- **Status: Shipped**

#### F2.3 — Conservation Analysis ✅

- Takes MSA output → conservation scores per position
- Visualized as score bars in results panel
- AI interpretation: which conserved regions may be functionally significant
- **Status: Shipped** (via pipeline v2)

#### F2.4 — Primer Design (from nucleotide alignment) ✅

- Input: nucleotide sequence
- Primer3 with configurable: product size, Tm, GC content, number of returns
- Reports: primer sequences (left/right), Tm, GC%, positions, product size, penalty
- No rate limits, runs locally via primer3-py
- **Status: Shipped**

#### F2.5 — Domain & Motif Analysis ✅

- Input: UniProt accession
- Fetches domain annotations from InterProScan API (Pfam, PROSITE, SMART, etc.)
- Displays: domain name, source DB, start/end positions, score
- **Status: Shipped**

#### F2.6 — API Key System ✅

- Generate scoped API keys (`sk_bio_` + `secrets.token_urlsafe(32)`)
- SHA-256 hashed storage (plaintext returned once at creation)
- `X-API-Key` auth middleware in services/auth.py
- Frontend: list keys with prefix badge + last_used_at, generate modal, revoke with confirmation
- **Status: Shipped**

#### F2.7 — Share Links & Export ✅

- Share: `POST /api/share` generates `secrets.token_urlsafe(16)` token, stores in jobs.share_token
- Frontend share button copies shareable URL to clipboard
- Export: `GET /api/export/job/{id}?format=pdf|json` returns StreamingResponse with Content-Disposition
- **Status: Shipped**

#### F2.8 — Guest → Account Upgrade ✅

- Guest sessions via `signInAnonymously()`
- Upgrade via `linkIdentity({ provider: 'google' })`
- Settings page shows upgrade card for guests, Google sign-in button
- **Status: Shipped**

#### F2.9 — Pipeline v2 Engine ✅

- 8-step in-memory pipeline: BLAST → UniProt → MSA → Phylo → Domains → Pathway Enrichment → AlphaFold → AI
- Thread-safe dict storage, polling via `/api/pipeline/v2/status/{job_id}`
- Configurable via `steps[]` param
- Progressive reveal in PipelineResults.tsx
- **Status: Shipped**

#### F2.10 — Documentation, Monitoring & Caching ✅

- `/learn` documentation site with 10+ topic pages and glossary
- First-run tutorial (5-step modal walkthrough)
- Sentry error monitoring (frontend `@sentry/nextjs` + backend `sentry-sdk`)
- Cache-hit tracking with `from_cache` flag on results
- `/api/admin/cache-stats` endpoint for cache metrics
- `@ttl_cache` applied to pathway enrichment and NCBI search methods
- **Status: Shipped**

---

### Phase 3 — Protein Structure & Visualization (Months 7–10)

**Goal:** Complete the sequence-to-structure workflow with full 3D visualization and structural analysis tools.

#### F3.1 — Structure Retrieval

- Input: protein name, accession number, or PDB ID
- Queries RCSB PDB REST API
- Displays: structure metadata (resolution, method, deposition date, organism, chains)
- 3D viewer rendered in browser using NGL.js or Mol*
  - Rotate, zoom, pan
  - Color by secondary structure, chain, B-factor, conservation
  - Toggle: cartoon, surface, ball-and-stick, ribbon modes
- Direct link to original PDB page for reference

#### F3.2 — Structure Prediction (AlphaFold)

- Input: protein sequence (from F1.2 or pasted)
- Queries AlphaFold EBI API
- Returns predicted structure with per-residue confidence (pLDDT) scores
- pLDDT color-coded in 3D viewer (dark blue = very high, orange/red = low confidence)
- AI interpretation: "Regions with low confidence scores suggest structural disorder or flexible loops, which may be functionally significant..."

#### F3.3 — Secondary Structure Prediction

- Input: protein sequence
- Queries PSIPred API
- Returns predicted helix (H), strand (E), coil (C) per residue
- Visualization: linear secondary structure diagram above the sequence
- Comparison view if experimental structure (PDB) is available alongside prediction

#### F3.4 — Structural Comparison (TM-Align / DALI)

- Inputs: two protein structures (PDB IDs, AlphaFold predictions, or uploaded PDB files)
- Queries PDBeFold or EMBL-EBI structural alignment service
- Results:
  - TM-score (0–1; >0.5 suggests same fold)
  - RMSD value with interpretation
  - Superimposed structure displayed in 3D viewer
  - Aligned residue pairs highlighted

#### F3.5 — Structural Analysis Suite

- Input: PDB structure (from retrieval or prediction)
- Available analyses (user selects):
  - **Ramachandran Plot:** phi/psi angles for all residues, interactive D3.js plot, outliers highlighted
  - **H-bond Analysis:** all hydrogen bonds listed with donor/acceptor, distance
  - **Salt Bridge Analysis:** charged residue pairs within distance threshold
  - **Secondary Structure Assignment (DSSP):** helix/sheet/coil assignment per residue
  - **Inter-atomic Distances:** user selects two residues, platform calculates distance
- All analyses run via BioPython DSSP wrapper or PDB REST API

#### F3.6 — Homology Modeling

- Input: target sequence (no known structure), template PDB structure (user selects or platform suggests from BLAST)
- Platform submits to SWISS-MODEL API or ModWeb API
- Returns modeled structure with QMEAN quality score
- Quality visualization: residue-level quality in 3D viewer
- Ramachandran analysis auto-run on resulting model

---

### Phase 4 — Drug Discovery & Design (Months 11–18)

**Goal:** Add ADMET screening, ligand-receptor docking, and pharmacophore analysis. This phase is compute-heavy and cost-intensive — approach after revenue or compute sponsorship is secured.

**Note:** Full AutoDock Vina docking requires server-side GPU/CPU compute. Plan cloud compute budget before building this phase. Estimated cost: ~$50–200/month for on-demand compute instances.

#### F4.1 — Compound Search & Retrieval

- Input: compound name, SMILES, InChI, or compound ID
- Queries PubChem REST API and ChEMBL REST API
- Returns: structure, molecular formula, molecular weight, known bioactivity data
- 2D structure rendered in browser (RDKit.js)

#### F4.2 — ADMET Property Prediction

- Input: compound SMILES (from F4.1 or user-provided)
- Integrates SwissADME (form-based submission, parse response) or pkCSM API
- Returns: Lipinski rule of five check, bioavailability score, BBB permeability, toxicity flags
- Traffic-light visualization: green/yellow/red for each property
- Lipinski violations explained in plain English

#### F4.3 — Molecular Docking

- Inputs: protein structure (PDB ID or predicted), ligand (SMILES or PDB format)
- V1: Submit to SwissDock web service (async job)
- V2 (with compute): Run AutoDock Vina on server
- Results: binding energy (kcal/mol), binding poses ranked by score
- Top 3 poses visualized in 3D viewer
- AI interpretation: "A binding energy of -8.5 kcal/mol indicates strong binding affinity..."

#### F4.4 — Pharmacophore Analysis

- Input: set of active ligands for a target (from ChEMBL or user-provided)
- Platform identifies common pharmacophoric features (H-bond donors/acceptors, hydrophobic regions, aromatic rings)
- 3D pharmacophore model displayed
- Virtual screening against PubChem compound library (limited scope at V1)

#### F4.5 — Drug Likeness Screening

- Input: list of compounds (SMILES list or CSV)
- Batch ADMET screening
- Ranked output with drug-likeness score
- Filter by: MW, LogP, H-bond donors/acceptors, rotatable bonds, PSA

---

## 11. Guided Wizard System Design

### Core Principle

The wizard never asks users to know what they want to do technically. It asks what they want to know biologically. The system maps biology questions to tool chains.

### Wizard Entry Points

```
Landing Page → "What do you want to do?"
    │
    ├── "Find sequences similar to mine"           → BLAST Wizard
    ├── "Compare two protein/DNA sequences"        → Pairwise Alignment Wizard
    ├── "Align multiple sequences and build tree"  → MSA + Phylogenetics Wizard
    ├── "Look at a protein's 3D structure"         → Structure Wizard
    ├── "Predict structure from sequence"          → AlphaFold Wizard
    ├── "Find drugs/compounds for a protein"       → Drug Discovery Wizard
    ├── "Understand a biological pathway"          → Pathway Wizard
    └── "I'm not sure" → Guided Discovery (AI-powered intent detection)
```

### Wizard Step Design

Each wizard step must contain:

1. **The question** — plain language, one thing per step
2. **Why we're asking** — one sentence explanation (collapsible)
3. **Example input** — pre-filled placeholder that demonstrates valid input
4. **Validation** — real-time format checking (is this a valid accession? is this a protein sequence?)
5. **Smart suggestions** — if user types a gene name, suggest full accession numbers from live lookup
6. **A "learn more" toggle** — expands to teach the concept (BLAST programs, E-value thresholds, etc.)

### Example: BLAST Wizard Flow

```
Step 1/4 → "Enter your sequence or its accession number"
           [Explanation] We'll look this up in NCBI or UniProt
           [Input] Paste sequence or type accession (e.g., NP_000509.1)
           [Validate] Detects sequence type (protein/nucleotide)

Step 2/4 → "What are you looking for?"
           ○ Similar proteins across all organisms
           ○ Similar proteins in a specific organism [dropdown]
           ○ Similar sequences in a specific database [dropdown]

Step 3/4 → "How sensitive should the search be?"
           ○ Fast (finds closely related sequences) [default]
           ○ Sensitive (finds distant homologs, takes longer)
           [Learn more] → explains E-value thresholds

Step 4/4 → Summary: "We're going to run blastp against NCBI nr database
           with E-value threshold 0.001 in Priya's sequence.
           This usually takes 5–8 minutes."
           [Run Analysis] button
```

---

## 12. Results Page System

### Layout Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  HEADER: What you asked → What we ran → Time taken          │
├───────────────────────┬─────────────────────────────────────┤
│  VISUAL RESULTS       │  AI INTERPRETATION PANEL            │
│  (left, primary)      │  (right, contextual)                │
│                       │                                     │
│  • Interactive table  │  Plain-language summary of what     │
│  • Sequence viewer    │  the results mean biologically      │
│  • 3D structure       │                                     │
│  • Phylogenetic tree  │  Key finding cards:                 │
│  • Pathway diagram    │  • Top hit: [organism, function]    │
│                       │  • Identity: X% (what this means)  │
│                       │  • Confidence: [high/medium/low]    │
├───────────────────────┴─────────────────────────────────────┤
│  ANNOTATED PARAMETERS: E-value ⓘ | Bit score ⓘ | Gap% ⓘ  │
│  (each ⓘ expands to plain-language explanation)             │
├─────────────────────────────────────────────────────────────┤
│  NEXT STEPS (contextual):                                   │
│  "Run MSA with top hits"  |  "View structure"  |  "Export" │
└─────────────────────────────────────────────────────────────┘
```

### Result Components by Workflow

| Workflow | Primary Visualization | Secondary |
|---|---|---|
| BLAST | Sortable hit table, graphical alignment map | E-value distribution chart |
| Pairwise Alignment | Color-coded alignment, dot plot | Score matrix |
| MSA | Block MSA viewer, conservation plot | Logo plot (if desired) |
| Phylogenetics | Interactive tree (phylotree.js) | Bootstrap support heatmap |
| Protein Structure | NGL.js/Mol* 3D viewer | Secondary structure diagram |
| Ramachandran | Interactive D3.js scatter plot | Outlier list with residue IDs |
| Docking | 3D viewer with binding poses | Energy ranking table |
| Pathway | Reactome/WikiPathways embedded map | Gene/protein list |

### Export Options (every results page)

- PDF report (AI-generated, lab-report format, ready to submit)
- Raw data (CSV for tables, FASTA for sequences, PDB for structures, Newick for trees)
- Share link (results stored server-side for 7 days)
- "Cite this analysis" — auto-generates methodology section for lab reports

---

## 13. AI Interpretation Layer

### Architecture

```
Raw tool output (JSON/XML/text)
        ↓
Structured result extractor (BioPython / custom parsers)
        ↓
Prompt template (workflow-specific context + structured data)
        ↓
Groq API (llama-3.1-8b-instant) → fast inline annotations (< 2s)
        ↓
Anthropic Claude API → full report generation (on user request)
```

### Prompt Design Principles

1. **Never fabricate.** All AI interpretation is grounded strictly in the actual tool output. Prompts instruct the model to not go beyond the data.
2. **Educational tone.** "This E-value of 4×10⁻⁶² means the match is highly significant — essentially impossible to be due to chance."
3. **Uncertainty is explicit.** "AlphaFold predicts this region with low confidence (pLDDT < 50), suggesting it may be structurally disordered."
4. **Actionable.** Every interpretation ends with a suggested next step.

### Interpretation Templates by Module

| Module | AI Output |
|---|---|
| BLAST | Paragraph: biological function of top hits, evolutionary implications, confidence |
| Pairwise | Paragraph: what conserved regions suggest functionally, alignment quality assessment |
| MSA | Conservation commentary, identification of functionally important positions |
| Phylogenetics | Clade interpretation, evolutionary distance commentary |
| Structure | Secondary structure content, notable features, comparison to known folds |
| Docking | Binding affinity interpretation, key interacting residues, drug-likeness commentary |

### Hard Constraints on AI Layer

- The AI layer **never overrides** the numerical output of tools
- All claims are qualified with confidence language
- The platform never uses the phrase "100% accurate" — only "faithful to tool output"
- AI interpretation is clearly labeled as "AI-generated explanation" in the UI

---

## 14. Onboarding & Learning System ✅

### Level 1 — First-Run Onboarding (triggered once) ✅

- 5-step interactive walkthrough on first login (TutorialWalkthrough component)
- Steps: ① Welcome & navigation ② Running an analysis ③ Understanding results ④ AI interpretation ⑤ Learning more
- Skip available; re-accessible from Settings page
- localStorage flag `bio-nexus-onboarding` persists completion
- **Status: Shipped**

### Level 2 — Contextual Tooltips (persistent throughout app) ✅

- Every field has a ⓘ icon that explains what it is and why it matters
- Every result metric has a ⓘ that explains it in plain language with example
- Implemented as LearnPopover component — inline `(?)` popover with explanation and "Learn more →" link
- Tooltips are written for someone who has heard of the concept but never used the tool
- Power users can turn tooltips off in settings
- **Status: Shipped**

### Level 3 — "Learn More" Panel

- On every results page: expandable side panel
- "What is an E-value?" | "Why does MSA matter?" | "What does RMSD tell you?"
- Each panel links to the relevant section in the platform's own documentation
- Curriculum-aligned: content maps to standard M.Sc. Bioinformatics syllabus topics

### Level 4 — In-App Documentation / Knowledge Base ✅

- Full documentation site at `/learn` (Next.js pages within the app)
- 10 topic pages: BLAST, Alignment, Domains, Phylogenetic Trees, Protein Structure, Pathway Analysis, Interactions, Primer Design, Utility Tools, Glossary
- Each topic: sections with headings, code examples, parameter explanations
- Glossary: A–Z of bioinformatics terms with plain-language definitions
- Search bar on docs landing page
- Sidebar nav item (BookOpen icon) linking to `/learn`
- **Status: Shipped**

### Level 5 — Practical Templates (Curriculum-Aligned)

- Pre-built workflow templates for standard bioinformatics practicals:
  - "Retrieve protein, run BLAST, align top hits, build tree"
  - "Predict structure, run structural comparison, Ramachandran analysis"
  - "Find compound for target, check ADMET, run docking"
- User selects template → wizard auto-populates based on template → user only provides their specific sequence/target
- Perfect for coursework where the method is fixed but the input is student-specific

---

## 15. Data Flow & Job Architecture

### Challenge

Many bioinformatics operations are inherently asynchronous. BLAST against NCBI nr: 5–15 minutes. AlphaFold prediction: 1–5 minutes. PHYLIP tree construction: 30 seconds to 5 minutes. The platform must not block the user during these operations.

### Job Lifecycle

```
User submits analysis
      ↓
FastAPI creates job record in Supabase (status: queued)
Assigns unique job_id
Returns job_id to frontend immediately
      ↓
Celery worker picks up job from Redis queue
Submits to external API (NCBI BLAST, EMBL-EBI, etc.)
Polls external job status (every 15–30 seconds)
      ↓
External job completes
Worker parses result
Stores structured result in Supabase
Updates job status: completed
Triggers AI interpretation generation
Stores AI interpretation
Updates job: fully ready
      ↓
Frontend polling (React Query, every 10s) detects completed status
Renders results page
```

### Caching Policy

| Data Type | Cache Duration | Cache Key |
|---|---|---|
| BLAST result | 24 hours | MD5(sequence + database + program) |
| UniProt record | 24 hours | Accession number |
| PDB structure | 7 days | PDB ID |
| AlphaFold prediction | 30 days | UniProt accession |
| Pathway data (Reactome) | 12 hours | Pathway ID |
| MSA result | 12 hours | MD5(sorted sequence set + algorithm) |

**Rationale:** Biological databases update daily (UniProt) to weekly (PDB), so caching with appropriate TTLs reduces API load and speeds up user experience significantly for common sequences.

### User Job History

- All completed jobs stored in Supabase linked to user account
- Jobs accessible from dashboard for 30 days
- User can re-open any past analysis, re-run with different parameters, or export
- Guest users: jobs stored in localStorage, prompted to create account to save permanently

---

## 16. Non-Functional Requirements

### Performance

- Wizard step transitions: < 200ms
- Sequence validation (client-side): < 100ms
- Job submission to queue: < 1 second
- Results rendering once data is available: < 2 seconds
- 3D structure load (NGL.js): < 5 seconds for typical PDB files

### Reliability

- External API failure handling: if NCBI BLAST fails, retry with EMBL-EBI BLAST automatically; alert user to delay, not error
- Partial results: if one step in a multi-step pipeline fails, show completed steps and report specifically which step failed and why
- Job retry: automatic retry 3× with exponential backoff for transient API failures

### Security & Privacy

- User sequences and analysis inputs are stored encrypted at rest (Supabase RLS + encryption)
- Sequences are never shared between users or used for any purpose other than the analysis the user requested
- India DPDP Act 2023 compliance: privacy policy, consent on signup, data deletion on request
- No genomic data treated as health data in V1 (no clinical sequences; educational/research only)
- API keys (NCBI, Groq, Anthropic) stored in environment variables, never exposed to frontend

### Accessibility

- All color coding has text/icon fallback (colorblind safe)
- Wizard is keyboard-navigable
- Screen reader annotations on all interactive visualizations
- Reduced motion mode for NGL.js animations

### Scalability

- FastAPI backend deployed on Railway with auto-scaling
- Redis job queue handles burst traffic — jobs queue gracefully rather than dropping
- NCBI API key required (10 req/s limit with key vs 3 without) — register API key before launch
- For Phase 3+ heavy usage: implement per-user rate limiting on expensive operations (BLAST, AlphaFold)

---

## 17. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| NCBI BLAST API rate limiting at scale | High | High | Use EMBL-EBI BLAST as primary; NCBI as fallback. Implement request queuing and per-user limits. |
| KEGG licensing conflict when monetizing | High | Medium | Use Reactome (primary) and WikiPathways (secondary) for all pathway features. KEGG only for academic/non-commercial tier. |
| External API downtime (NCBI, PDB, EBI) | Medium | High | Health check monitoring; graceful fallback messages; retry logic with alternative API sources. |
| AlphaFold API deprecation or rate limits | Medium | Medium | Cache predictions aggressively (30-day TTL). Build structure-upload alternative. |
| Compute cost overrun in Phase 4 (docking) | High | High | Gate Phase 4 behind paid tier. Use SwissDock (free) for V1 docking, not self-hosted AutoDock. |
| AI interpretation inaccuracy | Medium | High | All AI output labeled clearly as "AI-generated explanation." Never override numerical tool output. Add disclaimer. |
| Solo developer burnout / scope overrun | Very High | High | Strictly enforce phase boundaries. Phase 1 must ship before Phase 2 begins. No features from future phases in current phase. |
| SwissADME has no public REST API | High | Low | Use form-based HTTP submission with response parsing (maintained workaround). Fallback: pkCSM API. |
| EMBL-EBI web services occasional downtime | Medium | Medium | Cache recent results; show user "service temporarily unavailable" with EBI status page link. |

---

## 18. Milestone Roadmap

### Phase 1 — Foundation (Months 1–3)
*Goal: Ship MVP that handles BLAST + pairwise alignment end to end*

| Month | Milestones |
|---|---|
| Month 1 | Project setup. Next.js + FastAPI scaffold. Supabase schema. User auth. Sequence retrieval (NCBI Entrez + UniProt). Accession number lookup. Format detection and conversion. |
| Month 2 | BLAST integration (EMBL-EBI async). Job queue (Celery + Redis). Real-time job status polling. Basic results table. |
| Month 3 | Pairwise alignment (Needleman-Wunsch + Smith-Waterman via EMBL-EBI). Guided wizard for BLAST + pairwise. AI interpretation layer (Groq). Basic PDF export. Onboarding flow. |

**Phase 1 Launch Definition:** A student can enter an accession number, run BLAST, see results with explanations, and do a pairwise alignment in under 15 minutes.

---

### Phase 2 — Alignment & Phylogenetics (Months 4–6)

| Month | Milestones |
|---|---|
| Month 4 | MSA via ClustalOmega API. MSA viewer component. Conservation plot. |
| Month 5 | Phylogenetic tree (PHYLIP/IQ-TREE web API). phylotree.js tree renderer. Bootstrap support display. |
| Month 6 | Primer design from nucleotide alignment. Workflow: BLAST → shortlist → MSA → tree (auto-piped). Phase 2 results page with all visualizations. |

---

### Phase 3 — Protein Structure & Visualization (Months 7–10)

| Month | Milestones |
|---|---|
| Month 7 | PDB structure retrieval. NGL.js/Mol* 3D viewer integration. Structure metadata display. |
| Month 8 | AlphaFold prediction integration. pLDDT visualization. Secondary structure prediction (PSIPred). |
| Month 9 | Structural comparison (PDBeFold / TM-Align API). Ramachandran plot (D3.js). DSSP secondary structure assignment. |
| Month 10 | H-bond + salt bridge analysis. Homology modeling (SWISS-MODEL API). Structure quality report. Phase 3 results polish. |

---

### Phase 4 — Drug Discovery (Months 11–18)

| Month | Milestones |
|---|---|
| Month 11–12 | PubChem + ChEMBL integration. Compound retrieval + 2D structure display. ADMET screening (SwissADME + pkCSM). |
| Month 13–14 | Basic docking (SwissDock web API). Binding energy display. Docking pose visualization. |
| Month 15–16 | Pharmacophore analysis. Drug-likeness screening (Lipinski, Veber). |
| Month 17–18 | Full docking pipeline (self-hosted AutoDock Vina — subject to compute budget). QSAR basics. Phase 4 results page. |

---

### Parallel Track — Platform (Ongoing)

| Quarter | Milestones |
|---|---|
| Q1 | Core infrastructure, auth, job queue |
| Q2 | Documentation site, onboarding, practical templates, feedback system |
| Q3 | Performance optimization, caching layer, monitoring (Sentry + Uptime) |
| Q4 | University partnership outreach, feedback integration, accessibility audit |

---

## 19. Open Questions & Future Scope

### Open Questions (Resolve Before Phase 2)

1. **Compute for Phase 4:** What is the budget for a Railway/Render compute instance capable of running AutoDock Vina? This decision determines the docking architecture.
2. **Domain name:** BioFlow AI as the final name? Register domain early.
3. **Authentication:** Google OAuth (fastest) vs email-password vs both? Recommendation: Google OAuth for V1 using NextAuth, consistent with NutriScan.
4. **KEGG commercial licensing:** Define exactly when this becomes an issue — is the V1 platform ever monetized? If yes, remove KEGG immediately and rely solely on Reactome + WikiPathways.
5. **Lab report PDF template:** Design the PDF export template before Phase 1 ships. Students will use this for coursework submission — it must be formatted correctly.

### Future Scope (Post V1)

- **RNA-seq pipeline:** DESeq2/edgeR analysis, gene expression heatmaps
- **Genome browser:** UCSC/Ensembl integration for genomic context
- **Literature integration:** PubMed abstract retrieval linked to analysis results
- **Collaboration:** Share analyses with classmates or supervisors, with commenting
- **Instructor mode:** Faculty create template practicals, students submit analyses through the platform
- **Mobile app:** React Native for viewing results on mobile
- **Public API:** Allow other developers to build on BioFlow workflows
- **Grant applications:** BIRAC, DST NIDHI PRAYAS after platform has validated user base

---

## Appendix A — Bioinformatics Curriculum Coverage Map

Maps platform features to the standard M.Sc. Bioinformatics curriculum (JMI / DU equivalent):

| Curriculum Topic | BioFlow AI Feature | Phase |
|---|---|---|
| NCBI, ExPASy, EBI exploration | Sequence retrieval engine + database browser | 1 |
| FASTA, GenBank, FASTQ formats | File format converter (auto-detect + convert) | 1 |
| Pairwise alignment (NW, SW) | Pairwise alignment wizard | 1 |
| BLAST and variants | BLAST wizard | 1 |
| E-value, P-value interpretation | AI interpretation layer + inline tooltips | 1 |
| BLOSUM, PAM matrices | Parameter annotations in wizard | 1 |
| ClustalW / MSA | MSA wizard (ClustalOmega) | 2 |
| HMM / Pfam | Pfam domain search (Phase 2 addition) | 2 |
| PHYLIP, MEGA, phylogenetic trees | Phylogenetics wizard + tree viewer | 2 |
| Primer design from alignment | Primer design tool | 2 |
| PDB, CATH, SCOP databases | Structure retrieval + metadata display | 3 |
| PyMOL / structure visualization | NGL.js 3D viewer in browser | 3 |
| Ramachandran plot | Ramachandran analysis tool | 3 |
| H-bonds, salt bridges, distances | Structural analysis suite | 3 |
| Secondary structure prediction (DSSP, PSIPred) | Secondary structure prediction tool | 3 |
| Homology modeling | SWISS-MODEL integration | 3 |
| DALI / TM-Align structural comparison | Structural comparison tool | 3 |
| Drug design, docking, ADMET | Drug discovery module | 4 |
| QSAR | QSAR basics module | 4 |
| Pathway analysis (KEGG) | Pathway wizard (Reactome/WikiPathways) | 2 |

---

*Document maintained by: Samad | BioFlow AI*  
*Next review: After Phase 1 scope finalization*
