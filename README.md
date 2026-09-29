---
title: Bio Nexus API
emoji: 🧬
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# BioNexus

[![Security Scan](https://github.com/Samadsaifi14/bio-nexus-/actions/workflows/security.yml/badge.svg)](https://github.com/Samadsaifi14/bio-nexus-/actions/workflows/security.yml)
[![Deploy](https://github.com/Samadsaifi14/bio-nexus-/actions/workflows/deploy.yml/badge.svg)](https://github.com/Samadsaifi14/bio-nexus-/actions/workflows/deploy.yml)

BioNexus is an evidence-aware web workspace for integrated bioinformatics
analysis. It connects deterministic computation, reference-database retrieval,
workflow execution, provenance, figures and optional AI interpretation while
keeping the underlying scientific result authoritative.

The project is intentionally explicit about evidence classes. A retrieved
database record is not a prediction, a synthetic fixture is not biological
validation, a successful workflow run is not an accuracy benchmark, and an AI
explanation is not independent scientific evidence.

## Scientific model

BioNexus uses four operating principles:

1. **Result authority** — scientific values originate in the backend result or
   recorded reference evidence. Frontend components may format results but must
   not invent or silently recalculate scientific values.
2. **Provenance** — inputs, parameters, software/reference identity, execution
   state, artifacts and checksums are retained where the workflow supports them.
3. **Fail-closed boundaries** — missing evidence remains missing or
   `NOT_EVALUATED`; unsupported production paths are not replaced by a preview.
4. **Interpretation after evidence** — AI text is an interpretation layer over
   recorded evidence and remains subordinate to the deterministic/reference
   result.

See `SCIENTIFIC_RESULTS_STANDARD.md`,
`docs/VALIDATION_BOUNDARIES_2026-09-13.md` and
`docs/NGS_BENCHMARK_STATUS.md` for the machine and publication claim
boundaries.

## Analysis capabilities

### Sequence, similarity and evolution

- **Sequence utilities** — DNA/RNA/protein analysis with IUPAC-aware handling.
- **Pairwise alignment** — global and local alignment with validated coordinate
  and input contracts.
- **BLAST** — nucleotide/protein program routing with EMBL-EBI and NCBI
  provider evidence, explicit failure states and downstream scientific handoff.
- **Multiple-sequence alignment** — local MAFFT when available, EMBL-EBI
  alignment services, and an explicitly labelled in-process fallback.
- **Phylogeny** — supported tree-building and visualization paths with method
  and model provenance.

### Annotation and biological evidence

- **UniProt** — structured reference retrieval/search with reviewed status,
  gene/protein fields, GO evidence and accession provenance.
- **Domains and motifs** — InterPro/member-signature evidence and local/custom
  motif scanning with source classes kept distinct.
- **Pathways and interactions** — Reactome/KEGG and interaction evidence where
  returned by their source adapters.
- **Function evidence** — evidence-backed inference; absence of source evidence
  is not converted into an asserted function.

### Structure and molecular modelling

- **RCSB PDB retrieval** — experimentally deposited structures are identified as
  such.
- **AlphaFold DB retrieval** — predicted models are retrieved from AlphaFold DB;
  BioNexus does not relabel database retrieval as an in-app AlphaFold
  prediction.
- **ESMFold fallback prediction** — when invoked, de-novo prediction remains
  explicitly labelled as predicted evidence.
- **Structure analysis** — geometry-derived analyses, secondary structure,
  interfaces and structure comparison with source/model context.
- **Docking** — AutoDock Vina 1.2.7 execution with recorded poses, affinity,
  configuration and logs. The canonical 1STP-biotin redocking fixture produced
  a retained symmetry-aware heavy-atom RMSD of 0.7252 Å against a predeclared
  2.0 Å threshold; this validates that single pose-recovery fixture, not general
  docking accuracy or affinity prediction.
- **Molecular dynamics** — hosted OpenMM workflow in the currently declared
  implicit-solvent scope. It is not represented as equivalent to a validated
  explicit-solvent production protocol.
- **Molecular descriptors** — deterministic RDKit descriptors and explicitly
  labelled rule-based screening. Predictive/clinical ADMET claims require a
  separately validated model and remain outside the current evidence boundary.

### Sequencing and transcriptomics

BioNexus deliberately separates **exploratory preview** from **production
execution**.

The exploratory NGS path is a bounded, sampled implementation for teaching,
interface testing and deterministic controls. Sampling/truncation and
unevaluated stages are disclosed and are not promoted to production evidence.

Production WGS/WES plans pin **nf-core/sarek 3.10.0**. Production RNA-seq plans
pin **nf-core/rnaseq 3.26.0**. When a local, SLURM or AWS Batch executor is
explicitly enabled and passes preflight, BioNexus can submit the validated
Nextflow launch contract and inventory observed artifacts. Production execution
never falls back to the exploratory preview.

Production germline accuracy remains `NOT_EVALUATED` until a BioNexus-produced
callset is compared with a matched accepted GIAB truth set/confident regions.
The retained HG002 chr20 fixture verifies the truth-evaluation harness only.

For downstream differential expression, the retained GSE67196 benchmark uses
the official public count source for 8 healthy/control and 10 sporadic ALS
cerebellum samples and the BioNexus DESeq2 path. The retained condition-only
analysis is reproducible and hash-locked, but the experimental unit is recorded
as `NOT_DECLARED`; the result therefore does not establish an ALS biomarker,
causal biology or clinical validity.

## ScientificResult contract

Publication-critical endpoints are being standardized around the
`ScientificResult` contract:

```text
status            VALID | DEGRADED | NOT_EVALUATED | FAILED
method            executed scientific method
engine/version    implementation identity
parameters        effective parameters
results           authoritative values/tables
plots             plots tied to recorded source data
artifacts         retained files/checksums where available
provenance        source/execution metadata
warnings          limitations and degraded states
citations         method/reference sources
```

The validation registry distinguishes method/software verification from
external biological validation. A feature is not promoted because of UI state
or AI text.

## Architecture

```text
User input
   |
   v
Input validation and scientific routing
   |
   +--> deterministic/local engines
   |      alignment · Primer3 · RDKit · Vina · OpenMM · statistics
   |
   +--> reference/evidence services
   |      BLAST · UniProt · InterPro · RCSB PDB · AlphaFold DB · Reactome
   |
   +--> durable sequencing execution
          nf-core/sarek 3.10.0 · nf-core/rnaseq 3.26.0
          local · SLURM · AWS Batch
   |
   v
Scientific result + provenance + artifacts
   |
   +--> tables / plots / exports
   |
   +--> optional grounded AI interpretation
```

## Retained publication benchmarks

- **GSE67196 RNA-seq / DESeq2:** full public processed-count study benchmark,
  retained source mappings, design audit, tables, plot-source data, figures,
  versions and SHA-256 manifest.
- **1STP-biotin redocking:** retained AutoDock Vina 1.2.7 benchmark;
  symmetry-aware heavy-atom RMSD 0.7252 Å versus predeclared 2.0 Å criterion.
- **HG002 chr20 truth-evaluation harness:** real GIAB truth evaluation using an
  independent public query callset; validates the evaluator harness only.
- **Synthetic NGS portability fixture:** narrow deterministic regression and
  workflow-portability evidence only.

Benchmark definitions and claim boundaries live under `benchmark/` and
`docs/`.

## Repository layout

```text
bioai-platform/
  frontend/                  Next.js / TypeScript user interface
  backend/                   FastAPI scientific services and executors
benchmark/
  real_data/                 retained real-data benchmark definitions/manifests
  ngs-portability/           compact synthetic portability control
paper/                       manuscript support material and figures
docs/                        audits, validation boundaries and execution notes
SCIENTIFIC_RESULTS_STANDARD.md
MASTER_PLAN.md
techspec.md
```

## Local development

Frontend:

```bash
cd bioai-platform/frontend
npm ci
npm run dev
```

Backend:

```bash
cd bioai-platform/backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Run deterministic backend CI checks:

```bash
cd bioai-platform/backend
python -m pytest -q
python scripts/ci_validate.py
```

Production NGS execution requires separate executor configuration and staged
data/resources. See `bioai-platform/backend/NGS_PRODUCTION_EXECUTION.md`.

## Current validation boundary

The repository supports software/method verification for a growing set of
modules and retains real-data evidence where explicitly documented. It does
**not** currently support a claim of platform-wide biological accuracy,
superiority over Galaxy/nf-core, clinical validation, validated predictive
ADMET, or BioNexus germline variant-calling accuracy against GIAB.

Passing AI grounding means that generated text corresponds to recorded
evidence; it does not independently establish biological truth.

## Contributing

Setup, test commands and conventions are documented in
[CONTRIBUTING.md](CONTRIBUTING.md). Scientific changes should preserve the
result/provenance contract and must not silently strengthen a validation claim.

## License

[MIT](LICENSE)
