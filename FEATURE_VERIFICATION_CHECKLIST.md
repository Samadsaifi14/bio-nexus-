# Bio Nexus — Feature Verification Checklist

**How to use this file:** for each tool, click through the live app and tick every row. A row you can't tick is a missing feature you just found *before* a user did. Update "Last verified" when you finish a tool. Any tool not re-verified in 90 days is stale — see `DEFINITION_OF_DONE.md` §5.

**Audit priority** below is based on how detailed each tool's spec was in `MASTER_PLAN.md`/`IMPLEMENTATION_LOG.md`. A vague spec is a strong predictor of an incomplete build — those are marked 🔴 and should be audited first.

---

## 🔴 Protein Interactions — AUDIT FIRST (spec: "interaction lookup module")

*Last verified: never*

- [ ] Interaction partners list renders with source database attribution
- [ ] Confidence/evidence score shown per interaction (and explained via LearnPopover)
- [ ] Network graph visualization (or explicit decision that this tool is text/table-only, documented here)
- [ ] Filter by evidence type (experimental / database / text-mining / co-expression) — or documented as out of scope
- [ ] Export (JSON/CSV/image) works
- [ ] Loading / error / empty states present
- [ ] Chains from a BLAST/UniProt result (cross-tool entry point) or documented as standalone-only
- [ ] Appears in pipeline wizard step list, or documented as intentionally excluded
- [ ] `/learn` entry exists for interaction confidence scoring

## 🔴 Function Prediction — AUDIT FIRST (spec: "sequence → function inference endpoint + job status")

*Last verified: never*

- [ ] GO term output (molecular function / biological process / cellular component) — or documented as excluded
- [ ] EC number prediction for enzymes — or documented as excluded
- [ ] Confidence score per predicted function, using the same hedged-language rule as AI interpretation (`RULES.md` §6)
- [ ] Distinguished visually/in copy from UniProt's existing function field, so the two don't read as duplicates
- [ ] Loading / error / empty states present
- [ ] Export works
- [ ] `/learn` entry exists

## 🔴 Pathway Enrichment — AUDIT FIRST (spec: exists only as a pipeline step, no standalone feature list)

*Last verified: never*

- [ ] Standalone pathway search (not just as a pipeline wizard step) works
- [ ] Enrichment statistics shown (p-value, FDR, gene ratio) with LearnPopover
- [ ] Pathway diagram viewer renders and is interactive
- [ ] Reactome → WikiPathways fallback actually triggers and is visible to the user (per `RULES.md` §4 fallback transparency rule)
- [ ] Export works
- [ ] `/learn` entry exists

## 🔴 Sequencing Annotation — AUDIT FIRST (spec: "variant calling → annotation", no detail on annotation source)

*Last verified: never*

- [ ] Variant table shows position, consequence, and reference/alt allele clearly
- [ ] Annotation source is stated in the UI (what database/reference are variants being checked against)
- [ ] Consensus sequence download works
- [ ] QC report (pre/post trimming) renders, not just a pass/fail flag
- [ ] Job correctly appears on dashboard and is shareable
- [ ] Export works
- [ ] `/learn` entry exists for variant-calling terms (VCF fields, consequence types)

---

## 🟡 Docking — spec has good detail, verify export/edge depth

*Last verified: ___*

- [ ] Full Vina log viewer, no truncation (per your earlier requirement — confirm it shipped as scrollable panel, not truncated text)
- [ ] RMSD table (l.b./u.b.) renders correctly
- [ ] Run-config UI exposes exhaustiveness, num_modes, grid center/size
- [ ] Binding pocket / blind docking option, or documented as fixed-pocket only
- [ ] 3D viewer shows docked pose overlaid on receptor
- [ ] Export (PDBQT/SDF/log) works
- [ ] Job shows in `MAX_CONCURRENT["docking"]` correctly under concurrent load (cap = 2)

## 🟡 MD Simulation — spec has good detail, verify output depth

*Last verified: ___*

- [ ] Trajectory or endpoint structure downloadable
- [ ] Energy/RMSD-over-time plot, or documented as endpoint-only (no trajectory analysis)
- [ ] Force field / solvent selector matches the verified matrix in the spec (ff14SB/ff15ipq/ff19SB/amberfb15/CHARMM36 × OBC1/OBC2/GBN2)
- [ ] 25-min run budget enforced with clear user-facing timeout messaging, not a silent failure
- [ ] Job respects `MAX_CONCURRENT["md"] = 1`

## 🟡 ADMET — spec has good detail, verify all properties surfaced

*Last verified: ___*

- [ ] All RDKit descriptors listed in the original spec are actually rendered (not just a subset)
- [ ] Lipinski rule-of-5 pass/fail shown with reasoning, not just a badge
- [ ] Traffic-light coloring matches a documented threshold table (link from LearnPopover)
- [ ] Export works

## 🟢 BLAST — spec detailed, spot-check only

*Last verified: ___*

- [ ] Global/local mode toggle works
- [ ] DNA query support works alongside protein
- [ ] program/db/max_hits params all actually reach the EBI request
- [ ] "Align pair" from any hit works
- [ ] 65-min poll cap surfaces a clear timeout message, not a stuck spinner

## 🟢 UniProt / AlphaFold / Structure Suite — spec detailed, spot-check only

*Last verified: ___*

- [ ] UniProt: function, disease associations, active sites, organism all present
- [ ] AlphaFold: pLDDT coloring in 3Dmol.js viewer, confidence legend visible
- [ ] Ramachandran plot renders and is readable
- [ ] Secondary structure assignment shown
- [ ] Foldseek comparison returns results and handles no-hit case

## 🟢 MSA / Phylogenetics — spec detailed, spot-check only

*Last verified: ___*

- [ ] All 5 MSA methods (ClustalOmega/MUSCLE/Kalign/MAFFT/T-Coffee) actually produce different, correct output
- [ ] All 3 tree methods (NJ/UPGMA/ML) work
- [ ] Bootstrap replicates shown as a color scale, correctly
- [ ] SVG/PNG/Newick export all work (not just one of the three)

## 🟢 Domains — spec detailed, spot-check only

*Last verified: ___*

- [ ] Pfam/InterPro fetch works
- [ ] PROSITE raw-sequence scan works independently of InterPro
- [ ] Reviewed/organism UniProt filters actually filter

---

## Cross-cutting checks (apply to every tool above)

- [ ] Tool's job type has a `MAX_CONCURRENT` entry if long-running (`durable-worker-design.md` §4.3)
- [ ] Tool's output is included in PDF/JSON export (`/api/export/job/{id}`)
- [ ] Tool's job type is included in share-link support
- [ ] Tool appears (or is deliberately excluded, and that's documented) in the pipeline wizard's 8-step chain
- [ ] Tool has a Sentry-visible failure path, not a silent catch
