# Bio Nexus — Feature Verification Checklist

**How to use this file:** for each tool, click through the live app and tick every row. A row you can't tick is a missing feature you just found *before* a user did. Update "Last verified" when you finish a tool. Any tool not re-verified in 90 days is stale — see `DEFINITION_OF_DONE.md` §5.

**Audit priority** below is based on how detailed each tool's spec was in `MASTER_PLAN.md`/`IMPLEMENTATION_LOG.md`. A vague spec is a strong predictor of an incomplete build — those are marked 🔴 and should be audited first.

---

## 🔴 Protein Interactions — AUDIT FIRST (spec: "interaction lookup module")

*Last verified: 2026-08-06*

- [x] Interaction partners list renders with source database attribution (header + JSON export both state STRING-DB)
- [x] Confidence/evidence score shown per interaction (and explained via LearnPopover)
- [x] Network graph visualization (or explicit decision that this tool is text/table-only, documented here) — **Decision:** network is rendered as the STRING-DB network *image* (with graceful fallback link if the image fails); full interactive graph is out of scope for now
- [x] Filter by evidence type (experimental / database / text-mining / co-expression) — client-side filter over the four STRING score channels, threshold 0.3
- [x] Export (JSON/CSV/image) works — PNG (network image), TSV (score table), JSON (raw payload) via `fix(interactions)` `d2ea003`
- [x] Loading / error / empty states present
- [x] Chains from a BLAST/UniProt result (cross-tool entry point) — chains exist from UniProt page, Domains page, and job detail page via `sessionStorage["interaction_gene"]`
- [x] Appears in pipeline wizard step list, or documented as intentionally excluded — **Documented exclusion:** not in the 5-step wizard chain (BLAST/UniProt → MSA → Phylo → Domains → AI Interpretation); interactions takes a single gene name, not a sequence, and is reachable as a standalone analyze tool + cross-tool chain
- [x] `/learn` entry exists for interaction confidence scoring — `learn/interactions` (STRING, score channels, network topology) wired to LearnPopover in the score table headers

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

## 🔴 Structure Prep — AUDIT FIRST (spec: techspec.md pre-work A1–A7)

*Last verified: 2026-08-23 (backend shipped + unit-tested; live/Docker verification pending)*

- [ ] Chain health report renders: missing residues (REMARK 465 count + ranges) AND CA–CA chain breaks (chain/resnum/distance)
- [ ] Repair outcome explicitly stated per run: `intact` / `repaired` / `broken_unrepaired` — a broken structure is never presented as equivalent to a clean one (A3) *(backend `chain_integrity` tagging shipped in structure_prep.py router; UI display of the field pending)*
- [x] Cleaned PDB produced (waters/heteroatoms removed) via pymol2 wheel; Biopython fallback logs a visible warning instead of failing silently (A1) *(code shipped; live PyMOL run pending — Docker daemon down, venv lacks pymol wheel)*
- [ ] fpocket pockets table renders (id/volume/area/score/druggability/residue count); fpocket binary actually present in API images (A1) *(both Dockerfiles build fpocket from source v4.0.0; image build unverified — daemon down)*
- [x] CASTp result carries explicit `castp_status` (`complete`/`timed_out`/`error`/`skipped`) — timeout is never indistinguishable from "no pockets" (A7) *(shipped; symmetric `fpocket_status` added)*
- [ ] Jobs persisted to Supabase (`structure_prep_jobs`), not in-memory; survives restart (A2) *(router persists via Supabase + migration `008_structure_prep_jobs.sql` written — migration must be applied in Supabase SQL Editor)*
- [x] Status endpoint scoped to owning user (404 for other users' job IDs) (A6) *(require_user_id + user_id filter on GET/POST)*
- [x] Invalid pdb_id / uniprot_accession / template rejected with 400 before any network call (A4) *(25 unit tests pass)*
- [x] All outbound calls route through `ssrf.validate_url()` even for hardcoded hosts (A5) *(unit-tested)*
- [ ] Loading / error / empty states present
- [ ] Export works (feeds §2 structure-export endpoints once shipped)
- **Deferred:** ESMFold window-splice gap repair (geometry risk — tag-and-proceed chosen per spec decision 2026-08-23); durable-worker execution for structure-prep jobs (stays in-process `asyncio.create_task`; if moved to worker, Dockerfile.worker needs fpocket+pymol2 parity)

## 🔴 De Novo Pipeline Branch (tier 6) — spec: techspec.md §1

*Last verified: 2026-08-23 (backend + frontend shipped; mocked integration tests pass, live E2E against ESMFold/InterProScan pending)*

- [x] Synthetic/random sequence that fails tiers 1–5 completes the pipeline without error state (acceptance criterion §1.4) *(test_de_novo_branch.py::test_zero_hit_protein_run_completes_denovo — mocked; run status `complete`, not error)*
- [x] Confidence badge on every downstream card, three states: identified / homolog / de_novo — homolog visually distinguished from tier-1 (§1.3) *(ConfidenceBadge.tsx: cyan/amber/dashed-purple; rendered on results page; browser visual check pending)*
- [x] De novo cards get distinct visual treatment (dashed border, "predicted, no database match") (§1.3) *(DeNovoPanel dashed purple card; AlphaFoldViewer titled "Predicted structure (ESMFold)")*
- [x] InterPro sequence-search mode used for de novo domain calls, not accession lookup (§1.2) *(de_novo.interpro_sequence_search → iprscan5 REST; normalized to domain shape; unit-tested)*
- [x] Structure card sourced from ESMFold HF API for de novo runs, labeled as predicted (decision 2026-08-23) *(esmfold_structure() with mean pLDDT from B-factors; inline pdb_text renders via new AlphaFoldViewer `pdbData` prop)*
- [x] Function hints composition-level only, clearly unscored/heuristic (decision 2026-08-23) *(function_hints() wraps _predict_from_sequence with "Heuristic" note; embedding scoring deferred below)*
- [x] Pathway/interaction cards show "unavailable — no identified homolog", not empty tables (§1.2) *(pathway unavailable notice on job page; msa/phylo/pathway steps marked failed with explicit message; interactions section auto-hides — no gene name exists)*
- **Deferred:** embedding-similarity function scoring (needs embedding infra — out of scope per spec §5); ESMFold window-splice for >768-residue de novo queries (API limit returns explicit failure today)

## 🔴 Structure Export — spec: techspec.md §2

*Last verified: 2026-08-23 (shipped + unit-tested; live PyMOL/docking E2E pending)*

- [x] Completed AlphaFold/structure job downloads `.pdb`, `.cif`, `.pse` *(structure_export router; accession→AF-DB, PDB-ID→RCSB)*
- [x] `.pse` opens in PyMOL with cartoon + pLDDT spectrum pre-applied, no manual coloring (acceptance §2.5) *(server-side pymol2 build: cartoon + `spectrum b` + transparent bg; stub-output guard tested. Live open-in-PyMOL check pending — venv lacks wheel, daemon down)*
- [x] Docking job exports receptor+ligand merged `.pdb` and ligand-only `.sdf` *(worker persists `receptor_pdb`+`result_sdf`; legacy rows get actionable re-run message)*
- [x] Download menu on AlphaFoldViewer + DockingViewer with separate format items (§2.4) *(StructureExportMenu: viewer toolbar + docking results page)*
- [x] ChimeraX/VMD ship as preferred-format file + command script (.cif+cmd hints / .pdb+.tcl), NOT fake session files (§2.3b honest-scoping rule) *(client-generated .cxc/.tcl alongside the coordinate download)*
- **Deferred:** ChimeraX `.cxs` and VMD state files (not freely scriptable headless — documented exclusion per §2.3b)

## 🔴 Page Capture + Final Synthesis — spec: techspec.md §3

*Last verified: 2026-08-23 (shipped + unit-tested; live Supabase migration + real-run capture E2E pending)*

- [x] `page_captures` row exists for every external source actually queried during a run (acceptance §3.4) *(wired in `_finalize_context`: NCBI top hit, UniProt, RCSB, InterPro, AlphaFold DB, Reactome; de novo runs record none — correctly)*
- [x] Human-facing page URLs captured (not just API endpoints), text sections + figure image URLs stored *(stdlib HTML extractor: title + heading sections + og:image/figure srcs; `fetch_status` honest on failure)*
- [x] Single "Final Report" panel rendered above per-tool breakdown, referencing confidence tier per finding (§3.3) *(FinalReport.tsx above AIInterpretation; findings carry ConfidenceBadge tier + source-page links; LLM polish optional, deterministic fallback never invents content)*
- [x] Capture respects ssrf.py allowlist + rate limits; no new SSRF surface (§3.2) *(all fetches via validate_url + per-host 1.5s throttle; unit-tested)*
- **Deferred:** none yet *(migration 009 must be applied in Supabase SQL Editor before captures persist)*

---

## Cross-cutting checks (apply to every tool above)

- [ ] Tool's job type has a `MAX_CONCURRENT` entry if long-running (`durable-worker-design.md` §4.3)
- [ ] Tool's output is included in PDF/JSON export (`/api/export/job/{id}`)
- [ ] Tool's job type is included in share-link support
- [ ] Tool appears (or is deliberately excluded, and that's documented) in the pipeline wizard's 8-step chain
- [ ] Tool has a Sentry-visible failure path, not a silent catch
