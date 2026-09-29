# BioNexus Scientific Roadmap Status

This document is an implementation/validation ledger, not a marketing checklist. A capability is only marked **validated** when the repository contains an executed benchmark or external evidence satisfying a declared acceptance contract. Source code alone is **implemented**, not validated.

Status vocabulary:

- **IMPLEMENTED** — executable code/API exists and has deterministic regression coverage where practical.
- **IMPLEMENTED / VALIDATION PENDING** — code exists, but the relevant external benchmark or biological truth set has not yet been executed successfully.
- **PROTOCOL READY** — manifest/protocol exists; the end-to-end scientific run remains to be executed and archived.
- **PARTIAL** — a scientifically bounded subset exists; unsupported sub-capabilities are explicitly labelled unavailable/heuristic.
- **MISSING** — no production implementation yet.

## Phase status

| Phase | Current status | Evidence in repository | Remaining high-impact work |
|---|---|---|---|
| 1 Scientific foundation | IMPLEMENTED / VALIDATION PENDING | Immutable experiment IDs, lineage/versioning, git/software/container/environment/seed/parameter/input/output fingerprints, archive manifests, compare/clone/search, DOI-deposit metadata, provenance graph, eight-class evidence policy | Apply migrations in every deployment; validate archive/clone lifecycle against production storage; external DOI deposition is not minted automatically |
| 2 BBS-2 benchmarking | IMPLEMENTED / VALIDATION PENDING | Machine-readable BBS-2 registry for sequence, annotation, structure, docking, MD, NGS and AI; defined/executed/passed semantics; AI numeric/citation/unsupported-claim gates | Curate and execute large external fixture sets; many BBS-2 entries remain `defined`, not passed |
| 3 Statistics | IMPLEMENTED | Bootstrap CI, effect sizes, permutation testing, BH correction, ROC/AUC, PR, calibration, ANOVA, regression, power, diagnostics, Kaplan-Meier; sample-size/method metadata | Add exact distribution-specific inference where required rather than approximations; validate against R/SciPy reference fixtures |
| 4 Sequence / primers / phylogeny | IMPLEMENTED / VALIDATION PENDING | Alignment conservation, entropy, logo weights, variant mapping; motif/dotplot; primer hairpin/dimers/in-silico PCR/SNP overlap/multiplex screening; NJ/UPGMA/ML/bootstrap plus rooting/consensus/metadata overlay | Population-scale primer off-target databases and empirical multiplex validation; external phylogenetic benchmark corpus |
| 5 Structural biology | PARTIAL | Molecular viewer/inventory, Ramachandran, Foldseek structural alignment, contact maps, chain interfaces, SASA, mutation neighbourhood mapping, pocket tools | True physical electrostatic potential (APBS/PB) remains missing; current exposed-charge map is labelled a heuristic; deeper interface energetics still pending |
| 6 Docking | IMPLEMENTED / SINGLE-FIXTURE POSE RECOVERY PASSED | Vina/Gnina analysis plus retained `BBS1-DOCK-1STP-BTN` streptavidin-biotin redocking evidence: symmetry-aware heavy-atom RMSD 0.7252 A against a predeclared 2.0 A threshold; the earlier 1IEP sanitisation failure is retained as a failed fixture | General docking accuracy and affinity prediction remain unvalidated; execute larger redocking/cross-docking/affinity benchmark sets and retain persistent archives |
| 7 Molecular dynamics | IMPLEMENTED / VALIDATION PENDING | Staged OpenMM MD; RMSD/RMSF/Rg/SASA/H-bonds/contact maps/DCCM/PCA/free-energy landscape/keyframes | Long-timescale durable production validation and convergence studies against reference trajectories; secondary-structure timeline requires suitable topology/trajectory evidence |
| 8 NGS | PARTIAL / REAL-DATA EVALUATION EVIDENCE EXISTS | WGS/WES staged QC plus pinned nf-core/sarek production planner; retained HG002/GRCh38 chr20 GIAB/hap.py evaluation harness run for a public DeepVariant callset; pinned nf-core/rnaseq 3.26.0 planner; retained full GSE67196 18-sample downstream DESeq2 execution with source/result/figure hashes | BioNexus-produced Sarek callset still requires matched GIAB evaluation; upstream FASTQ-to-count RNA-seq production execution and dedicated validated fusion workflow remain pending |
| 9 Evidence-aware AI | IMPLEMENTED / VALIDATION PENDING | Evidence graph, evidence classes, numeric fidelity, citation fidelity, unsupported-claim rejection, confidence/source/version/timestamp semantics | Expert-scored biological correctness benchmark at scale; continuous model-version evaluation |
| 10 Publication system | IMPLEMENTED / VALIDATION PENDING | Methods/results/figures/supplement/statistics/data/code availability generation; Nature, Nature Computational Science, Nature Methods, Bioinformatics, BMC Bioinformatics, NAR Web Server, IEEE render targets | Journal submission-schema edge cases and author-driven discussion remain human-review responsibilities |
| 11 Figure generation | IMPLEMENTED | Canonical SVG plus server-side PNG/PDF/TIFF, raster 300-600 DPI, checksums/export metadata | Data-dependent scale bars/statistical annotations must only be emitted when underlying result provides the required units/tests |
| 12 Reproducibility export | IMPLEMENTED / VALIDATION PENDING | Docker/pip/Conda/CITATION.cff/RO-Crate/software manifest/checksums/Zenodo-ready bundle | End-to-end deposition test on Zenodo sandbox/real repository |
| 13 Data management | IMPLEMENTED / VALIDATION PENDING | Versioned dataset library, snapshots, checksums, lineage, ground-truth distinction | Larger curated ground-truth library and remote object-store lifecycle policies |
| 14 Documentation | PARTIAL | API/user/engine documentation, learn pages, scientific standards, generated docs tooling, this ledger | Every new scientific endpoint still needs linked UI help/examples and parameter-level documentation validation |
| 15 Security/compliance | IMPLEMENTED BASELINE | Authentication/RLS, audit logging, SSRF protections, Semgrep, CodeQL, pip-audit/npm audit, secret/environment patterns | Formal organizational retention/privacy procedures and regulated-compliance certification are outside source-code claims |
| 16 CI/CD & quality | IMPLEMENTED BASELINE | Frontend build/type gate, BBS-1, BBS-2 foundation gate, NGS/MD suites, security workflows | Add performance baselines and production-scale benchmark runners with artifact retention |
| 17 Real scientific demonstrations | PARTIAL / RETAINED REAL-DATA RUNS | Retained GSE67196 downstream RNA-seq statistical execution, retained HG002 chr20 truth-evaluation harness run, and retained 1STP-biotin docking pose-recovery benchmark; each has explicit claim boundaries and checksums | Complete additional end-to-end public cases, use persistent DOI-backed archives, and execute production caller/workflow benchmarks before broad accuracy claims |
| 18 Comparative evaluation | PROTOCOL READY | Objective comparison protocol/evaluator; no subjective UI superiority scoring | Execute the same pinned workloads on BioNexus and comparison platforms and publish raw evidence plus uncertainty |

## Submission gate

BioNexus should not be described as externally validated, clinically validated, or superior to established platforms until the following are all true:

1. BBS-2 external benchmark runs are archived with immutable checksums and acceptance decisions.
2. At least three end-to-end real biological case studies are executed from public inputs and reproduced from exported bundles.
3. GIAB/GA4GH evaluation is completed for a **BioNexus-produced production germline callset** on matching confident regions; the retained public-DeepVariant chr20 evaluator run does not satisfy this gate.
4. SEQC or another accepted RNA-seq reference study is executed through the pinned **upstream production RNA-seq workflow**; the retained GSE67196 downstream DESeq2 run does not by itself satisfy FASTQ-to-count production validation.
5. Comparative platform evaluation uses identical declared inputs/versions/criteria and reports failures as well as successes.
6. The full CI/security suite is green for the release commit.

The scientific rule is: **implemented != benchmarked != validated != clinically validated**.
