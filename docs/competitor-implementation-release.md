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
