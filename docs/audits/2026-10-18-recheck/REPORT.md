# BioNexus complete recheck — 18 October 2026

**Audit finished; product is not all-green.** All 25 catalog pages rendered. All 140 backend test modules were attempted locally, with uncompleted modules explicitly blocked. Interpretation was checked as a 26th feature. No scientific implementation was changed during this audit.

Production inspected: `18ae7b602e34a52259434ee66fd0ac2d99c28934`. Fresh CI ran `ae77a4fe1b9e55f2a5c7034009952f4a9a5bade2`, whose only differences from production are two verification documents; scientific code is identical.

## Fresh checks

- Full backend CI [job 117730721829](https://github.com/Samadsaifi14/bio-nexus-/actions/runs/39066715514/job/117730721829): **1,537 passed, 4 failed, 40 skipped**, finished 17:02 UTC. Failures remain failures. See `fresh_full_ci.json`.
- Local frontend lint, production build, interpretation contracts and RNA-seq plot contracts: **PASS**; separate retained logs. Build used local verification settings and placeholder public service configuration.
- Native BLAST: **9 tests passed, Swiss-Prot recovery 8/8**. Canonical redocking passed, but the 10-complex panel **FAILED, 2/10**. Fresh native evidence and timestamps: `native_ci_evidence.json`. Other successful jobs copied into rerun attempts are not claimed as fresh.
- Native remote R: GO/fgsea/recovery and 221-gene SALS regression passed; final numeric QC/tximport group **6 passed**.
- Live production RNA-seq, pairwise, TP53 PPI and Aspirin ADMET completed. Every other page received a rendering/input-form check and mapped regression review, not a new native scientific run.
- Local completed-case totals (latest attempts only): {"passed": 1345, "error": 2, "skipped": 20, "failure": 4}. See `local_module_results.json`; deadlines and skipped cases are not successes. Module isolation is diagnostic and cannot replace the full CI gate.

## Every feature

UI PASS means its page rendered, not that its entire roadmap is implemented. Regression module counts overlap across rows; do not sum them. Test selection patterns and filters are in `feature_manifest.json`. Every row also carries SCOPE-01.

| # | Feature | UI | Latest local regression modules | Marked hindrance | Remaining implementation/validation scope |
|---|---|---|---|---|---|
| 1 | RNA-seq | PASS | 15 PASS; 2 FAIL/ERROR | PLOT-01, DATA-01, PROV-01, METHOD-01 | Full FASTQ-to-count production execution and SEQC truth-set parity are separate from the successful live count-matrix case. Uploaded teaching counts have no independently established raw-read provenance. |
| 2 | Consensus sequencing | PASS | 3 PASS | SCOPE-01 | Synthetic/compact-reference fixtures do not certify genome-scale calling, ClinVar/VEP completeness or clinical accuracy. |
| 3 | BLAST | PASS | 9 PASS; 1 BLOCKED: module deadline | PROVIDER-01, ENV-01 | Remote NCBI availability remains an external dependency. Custom uploaded databases, DIAMOND and broad-taxonomy production workloads are not certified by Swiss-Prot positive controls. |
| 4 | Pairwise alignment | PASS | 3 PASS | SEC-01, UI-01 | Live sample alignment completed. Comprehensive UniProt feature-track overlays and permutation-calibration parity are not established by this sample. |
| 5 | Multiple sequence alignment | PASS | 5 PASS | SCOPE-01 | A full editable alignment workspace and large benchmark corpus remain outside the observed page and regression checks. |
| 6 | Phylogenetics | PASS | 4 PASS | SCOPE-01 | IQ-TREE adapter tests do not establish executed ModelFinder selection or external evolutionary-tree accuracy. |
| 7 | Domains | PASS | 2 PASS | SCOPE-01 | Domain-to-MSA overlays and multi-homolog architecture comparison were not demonstrated end to end. |
| 8 | Motif scanner | PASS | 2 PASS | SCOPE-01 | Pattern scanning is distinct from MEME-style de novo motif discovery; discovery/enrichment validation was not established. |
| 9 | UniProt | PASS | 4 PASS | SCOPE-01 | Full record-track/link integration and arbitrary-source availability require representative live runs beyond unit fixtures. |
| 10 | Sequence utilities | PASS | 4 PASS | SCOPE-01 | The observed UI offers 13 curated enzymes. A full enzyme catalog, codon-usage comparison and cloning equivalence are not certified. |
| 11 | Dot plot | PASS | 1 PASS | SEC-01 | Genome-scale minimap2/MUMmer alignment plotting was not established. A pairwise bridge currently embeds sequence input in its URL. |
| 12 | Structure analysis | PASS | 3 PASS; 1 FAIL | ENV-03 | A MolProbity/wwPDB-equivalent full clash/rotamer validation and physical APBS electrostatics have not been established. |
| 13 | Structure preparation | PASS | 2 PASS | SCOPE-01 | PDB2PQR/PROPKA protonation, PDBFixer missing-atom repair and licensed loop modeling are not certified by cleanup tests. |
| 14 | Pocket analysis | PASS | 2 PASS | DOCK-01 | The redocking panel shows five first-ranked-pocket/site mismatches. P2Rank and calibrated druggability were not established. |
| 15 | Structure comparison | PASS | 1 BLOCKED: module deadline; 1 PASS | SCOPE-01 | Binding-site/ligand superposition and a representative external US-align/Foldseek benchmark remain unverified. |
| 16 | Structure prediction | PASS | 1 PASS; 1 BLOCKED: module deadline | ENV-01 | The visible tool is ESMFold. ColabFold/Boltz complex/ligand prediction and new-sequence experimental validation are not established. |
| 17 | SWISS-MODEL | PASS | 1 PASS | SCOPE-01 | Repository lookup does not implement a new template-selection/alignment/MODELLER/refinement workflow. |
| 18 | Molecular dynamics | PASS | 8 PASS | SCOPE-01 | The hosted UI caps production at 20 ps. Long convergence, explicit-solvent production and MM-GBSA are not certified. |
| 19 | Function hints | PASS | 1 BLOCKED: module deadline; 4 PASS | SCOPE-01 | Evidence counts are not functional probabilities. eggNOG/DeepFRI-equivalent performance and novel-function correctness remain unverified. |
| 20 | Docking | PASS | 9 PASS | DOCK-01–03 | Fresh full panel failed 2/10: five pocket-site failures, two chemical-parsing failures and one RMSD failure. No affinity or screening-accuracy claim. |
| 21 | ADMET | PASS | 4 PASS | ADMET-01, CHART-01, UI-01 | Source labels ADME/toxicity as heuristics, not trained ADMET-AI models. Applicability-domain and external predictive accuracy remain unverified. |
| 22 | Pathway analysis | PASS | 4 PASS | SCOPE-01 | Causal-network/IPA equivalence is not established. The UI offers KEGG, while RULES.md restricts KEGG use in a monetized fallback; commercial configuration/terms need review. |
| 23 | Protein interactions | PASS | 1 BLOCKED: module deadline; 1 PASS | PPI-01, UI-01 | Live result returned 12 partners. UI scale text is stale and unrelated docking copy appears. Full community/network/export parity is not certified. |
| 24 | Primers | PASS | 3 PASS | SCOPE-01 | Supplied-template/in-silico PCR does not establish genome-wide primer-BLAST specificity or laboratory PCR success. |
| 25 | Utility tools | PASS | 2 PASS | SCOPE-01 | EMBOSS-scale converters and full FASTA/GenBank/GFF validation breadth are not certified. |
| 26 | Interpretation and evidence | PASS (PPI result) | 5 PASS; 1 FAIL/ERROR | AI-01, ENV-03 | Live PPI explanation raised a numeric grounding warning for its 12-item count. Grounding is distinct from expert-reviewed biological correctness. |

## Hindrance register

| ID | Status | Area | Evidence and next action |
|---|---|---|---|
| DOCK-01 | P1 / OPEN | Docking and pockets | Redocking remains 2/10. First-pocket site offsets: 1IEP 59.0 Å; 2F12 10.1 Å; 1GKC 19.4 Å; 1Q4T 19.5 Å; 1P62 9.7 Å. Correct site selection and rerun the unchanged panel. |
| DOCK-02 | P1 / OPEN | Docking | 1OYT docked SDF and 1UYG reference SDF could not be parsed. Repair chemical conversion, retaining failed artifacts. |
| DOCK-03 | P1 / OPEN | Docking | 2H4G top-mode RMSD 7.366 Å fails 2 Å criterion. Passing cases: 1STP 0.856 Å and 1HVR 0.515 Å. No threshold was relaxed. |
| AI-01 | P2 / OPEN | Interpretation | Live TP53 explanation warns that count 12 cannot be traced, although 12 partners are displayed. Investigate derived-count grounding; biological correctness is not established by successful generation. |
| SEC-01 | P1 / OPEN | Pairwise → dot plot | Bridge embeds full sequences in seq_a/seq_b URL parameters. Public p53 fixtures exposed the mechanism; no private-data disclosure was established. Replace with an opaque run reference or payload transfer. |
| ADMET-01 | P1 / OPEN | ADMET | Selecting Caffeine changes input but leaves Aspirin C9H8O4 / 180.16 results visible. Example handler only calls setSmiles; clear or explicitly label previous results when input changes. |
| CHART-01 | P2 / OPEN | ADMET | Generic Min vs Value scatter mixes six radar descriptors with different units and lacks descriptor labels/normalization. Use a descriptor-aware plot. |
| PPI-01 | P2 / OPEN | PPI | UI says STRING native 0–1000 scores were normalized, while adapter preserves REST confidence on 0–1. Correct displayed provenance. |
| UI-01 | P3 / OPEN | PPI, pairwise, ADMET | Generic result footer discusses docking score/displacement charts on unrelated tools. Render tool-specific help. |
| PLOT-01 | P2 / OPEN | RNA-seq exports | Native expression and sample-distance PNGs have colliding legends and clipped condition labels. PCA labels also crowd. Inspect all export formats after layout repair. |
| DATA-01 | QC WARNING / REVIEW | RNA-seq GSE336901 | Library size spread is 270.654× (45,116–12,210,825); size factors 0.0457–10.032; 5 samples/group. UI warnings are present. Review depth/outliers and design; a completed run is not biological validation. |
| PROV-01 | VALIDATION GAP | Uploaded teaching counts | Checksum and arithmetic match the teaching fixture; independent raw-read provenance and a fresh full uploaded-matrix DESeq2 fit were not established. |
| METHOD-01 | DISCLOSED DIFFERENCE | RNA-seq | Implementation uses DESeq2 normal-prior shrinkage; lecture mentions apeglm. These methods are not interchangeable. UI discloses its method. |
| PROVIDER-01 | BLOCKED / OPEN | Remote BLAST | Fresh full CI: 4 failures (2 timeouts and 2 reliability/loop assertions); NCBI queue estimates 8,530–8,703 seconds. Native Swiss-Prot 8/8 controls passed; they do not close remote reliability failures. |
| ENV-01 | BLOCKED / OPEN | Local suite | Monolithic run stalled and was interrupted (130). All 140 modules were subsequently attempted with OS deadlines. Deadline modules: test_de_novo_branch.py, test_feature_validation.py, test_fuzz_random.py, test_blast_comprehensive.py. Unfinished cases are not passes. |
| ENV-02 | RESOLVED / RETESTED | Local proxy | Installed missing socksio via httpx[socks]. Retried affected modules; retained original failures and later outcomes. |
| ENV-03 | RESOLVED SETUP; DNS OPEN | Local fixture/export checks | Created missing basetemp parent and reran 3 modules: 33 passed, 2 structure-export failures. SSRF hostname resolution blocks those 2 checks. Page-capture DNS failures also remain. No SSRF guard was disabled. |
| ENV-04 | LOCAL BLOCKER; REMOTE SUBSET PASS | R runtime | Rscript absent locally; apt installation denied setgroups/seteuid/setegid. Native remote R/DESeq2/GO known-answer and 221-gene SALS fixture checks passed. This does not establish a fresh full uploaded-matrix fit. |
| SCOPE-01 | UNVERIFIED / PER FEATURE | All roadmap items | Every row below lists remaining scope. Page rendering, mocked contracts and native positive controls do not certify all competitor capabilities, clinical validity, commercial licensing or live cross-tenant authorization. |

## RNA-seq and attachments

Read all 100 slides across four supplied decks and inspected `05CerSALSinput.txt`. Attachment hashes are retained in `attachment_inventory.json`. The count matrix SHA-256 is `b7a9736672a6cebfdeea78dd151f5c764b058537cac09aeb0256cbfb7123dc08`, exactly matching the repository teaching fixture. Independent arithmetic found 22,085 genes, 18 samples (8 healthy, 10 SALS), finite nonnegative integer counts, no duplicate IDs, 20,169 retained genes at ≥10 counts in ≥8 samples, and all 18 lecture size factors matching at 3 decimals. This is arithmetic verification, not independent provenance or a fresh complete DESeq2 refit.

Fresh production GSE336901: 42,000 input genes, 10 samples; 14,343 retained, 124 DEGs (32 up, 92 down); GO ORA completed. The 17,154,654-byte downloaded bundle has 52 members. All **51 indexed files** matched SHA-256 and byte size; ZIP CRC, filter, normalized-count arithmetic, DEG selection/directions, and analysis-script checksum checks passed. Maximum normalized-count discrepancy was 3.49e-10. Seven SVGs parsed, seven PNGs decoded, seven PDFs had valid headers; PDFs were not fully rendered. All seven PNG families were visually inspected; the two heatmap layout failures are retained as images. See `live_rnaseq_bundle_checks.json`.

## Evidence and limits

Full per-module logs/JUnit, local runtime logs and the interrupted-run log are retained in the local audit folder. The repository publishes the summary JSON, final retry XML, selected frontend logs, browser evidence and failure images.

- `browser_pages_and_ppi.json`: all 25 page snapshots and live PPI/AI evidence.
- `browser_live_rnaseq_pairwise.json`: sanitized RNA-seq/pairwise output.
- `browser_admet.json` and `browser_admet_stale_result.json`: completed Aspirin output and Caffeine input with stale Aspirin output.
- `interpretation_grounding_warning.jpg`, `observed_expression_heatmap.png`, `observed_sample_distance_heatmap.png`: visible failures.
- `backend/` and `backend-retry/`: original and retry JUnit/log evidence. `final-fixture-retry.xml`: final 33-pass/2-fail fixture correction.
- Native executables not available locally, timeouts, skipped tests and mocked adapters remain distinguishable from executed production/native checks. No live multi-tenant authorization test or independent scientific review was performed. Signed artifact URLs and downloaded private run bundles are excluded.

This report marks the hindrances; it does not claim to repair them or complete every original paid-tool capability.
