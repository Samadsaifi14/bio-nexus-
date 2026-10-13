# Competitor-inspired implementation release

## Implemented

- REA 6.4.0 developer-tool setup is pinned independently of production dependencies.
- Function evidence keeps genuine InterProScan/InterPro2GO retrieval. Failed mappings are unavailable evidence; signature IDs are not treated as InterPro accessions. The UI supports structured GO terms and removes unsupported DeepFRI/confidence claims.
- Pocket analysis has explicit fpocket or exploratory SASA selection. Engine failure never switches methods automatically. Native descriptors are matched exactly, missing metrics remain null, and Total SASA is labelled as native fpocket output. Structure preparation shares the parser.
- Primer design, pair QC and multiplex QC use Primer3 2.3.1 with recorded salts, magnesium, dNTPs, DNA concentration and temperature. Missing thermodynamics produces an explicit failure, not an approximation.
- The sequence workspace includes linear/circular restriction maps for 13 enzymes, both-strand/type-IIS cleavage, origin-spanning recognition, digest fragments and evidence JSON. Changed inputs invalidate prior results and in-flight responses.
- Owned job results have a workflow evidence JSON download with states, dependencies, versions, input identity, provenance gaps and a canonical checksum. This is an evidence format, not an executable external workflow.
- Every listed competitor is mapped to official documentation and current source paths in the capability audit. Unsupported blanket comparison claims were corrected.

## Verification

**130 selected regression tests passed.** Selected suites: function research-grade evidence, native pocket parsing/provenance, pocket detection, scientific hardening, primer QC, multiplex primer QC, workflow manifests, reproducibility ledgers, restriction maps and sequence utilities.

The production frontend build and TypeScript checks passed. A real fpocket executable built from upstream tag 4.2.3 processed its 1UYD sample through BioNexus and returned 13 pockets without fallback. The executable reports version 4.0; the tag and reported version are deliberately recorded separately in `fpocket-integration-check.json`.

REA inspected the generated frontend artifact but parsing stopped because the host's process ownership inspection (`ps`) fails. Its partial evidence identity and boundary are in `rea-artifact-inspection.json`. This is not a completed REA reconstruction. Browser interaction checks could not run: Chrome was absent, installation required unavailable OS operations, and the portable browser download returned an invalid archive. No visual QA or production end-to-end execution is claimed.

## Remaining boundaries

No commercial application binaries were supplied or reconstructed. These changes do not implement full Galaxy, Geneious, CLC, Benchling, OmicsBox, cloud-workflow or commercial drug-discovery suites. Enterprise tenancy/compliance, external workflow adapters, clinical validation, affinity/FEP parity, a new function ML model and independent multi-platform benchmark superiority are not established. Existing production genomics/docking/MD workflows were retained; no synthetic result was substituted for external execution.

Backend changes require deployment of this revision and its required Primer3 dependency. The existing Docker build already installs fpocket from a pinned upstream tag. A frontend push alone does not verify deployment of that backend.

## Second implementation increment (2026-10-13)

The following missing capabilities were implemented in the application, with API and user-facing controls:

| Competitor group | Delivered capability | Explicit boundary |
|---|---|---|
| Galaxy | Portable built-in protein workflow recipes, import validation and queued replay with original input SHA-256 checks | BioNexus recipe format; no Galaxy `.ga` import and no pinned remote database replay guarantee |
| Geneious Prime | Annotated GenBank export with strict strand/coordinate handling | No new sequence assembler or licensed algorithm reconstruction |
| CLC Genomics Workbench | Tested existing input contracts and exposed retained RNA-seq execution monitoring | No new industrial/clinical validation or production compute deployment |
| Benchling / SnapGene | Linear/circular annotated DNA and origin-crossing/reverse-strand GenBank exchange alongside restriction maps | User annotations unverified; cloning simulation and ELN not implemented |
| OmicsBox | GMT custom gene-set analysis with explicit experimental universe, hypergeometric testing and BH over all eligible terms; TSV/evidence exports | Caller-declared annotation release/species/namespace; no bundled database/ontology propagation |
| Latch / Basepair / Partek Flow | Owner-scoped retained RNA-seq jobs, retry counts, stale heartbeat, resumption and transactional queued/QC cancellation | Running process termination unavailable; no newly provisioned distributed compute |
| Schrödinger / MOE / Discovery Studio | All-pose water-contact geometry, water/atom identity, input hashes, evidence export; heavy-atom RMSD and AutoDock element normalization | Geometric contacts, not energetic hydrogen-bond validation, affinity, FEP or symmetry-aware RMSD |
| Seqera / DNAnexus / Terra | Validated replay recipes and private job lineage through existing worker | No external platform API adapters, WDL executor or enterprise compliance claim |
| LLMs / bio-agents | Single-tool explanation schema/numeric fidelity enforcement, retry of invented-number responses, input digest/model identity, missing-evidence rejection | Numeric token presence does not verify units, semantic truth, causality or efficacy; no new general autonomous agent |

### Executed verification

250 selected regression tests passed across these changes and prior function/pocket/primer/provenance/NGS/count contracts. Final frontend TypeScript and local production build passed using `BIONEXUS_LOCAL_VERIFY=1 NEXT_TELEMETRY_DISABLED=1`. The standard Sentry-enabled build was rejected by automatic approval review for telemetry egress; local verification uses the existing no-upload configuration. Browser interaction QA and authenticated live provider execution were not performed.

Stale tests were repaired to exercise the documented signed-frame and strict invalid-base contracts. The fpocket-grid fixture now supplies a valid receptor atom rather than `ATOM` without coordinates; malformed receptor rejection remains in production.

### REA evidence and unresolved original scope

REA was invoked on Galaxy's actual publicly served 6.8-MB `analysis.bundled.js`, with checksum and full partial inventory evidence retained in [rea-galaxy-inspection.json](rea-galaxy-inspection.json). Semantic parsing stopped at the host's procps process-ownership failure. A recorded public Galaxy configuration response was also submitted to REA's network-capture inspector; it hit the same host prerequisite. No repeated installation or process-safety bypass was attempted. These failures are not completed competitor reconstructions.

Other proprietary applications were not supplied as installed runtimes or binaries. Their code and behavior were not reverse engineered by REA. The broader requested reconstruction of every competitor remains incomplete; this increment closes concrete application gaps through independent implementations. Full execution/validation requires a compatible REA host plus the actual selected commercial artifacts or accessible runtimes, reviewed test workloads, and configured production workers. Frontend GitHub publication does not verify backend deployment, durable volumes, R/Nextflow dependencies, Supabase migration application or cloud resource access.

Sources and details: [capability audit](competitor-capability-audit.md), [workflow replay contract](workflow-replay-contract.md), [custom enrichment](custom-gene-set-enrichment.md), [SnapGene GenBank export](https://support.snapgene.com/hc/en-us/articles/10383703194004-GenBank-Export-Customization), [Biopython sequence annotation](https://biopython.org/docs/latest/Tutorial/chapter_seq_annot.html).
