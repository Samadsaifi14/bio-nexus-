# Paper-backed engine work and completion loop

This branch preserves the original roadmap and adds independently implemented engine capabilities. It does not copy competitor interfaces or claim reconstructed proprietary engines.

## Delivered changes

| Area | Change | Method and verification boundary |
|---|---|---|
| NGS / Nextflow | Owner-scoped process trace monitoring and JSON export; complete rows only, cached/failed tasks distinguished | Real Nextflow trace format. Parser/ownership tests pass; this is not proof of a deployed Nextflow executor. Remote S3 trace monitoring remains unavailable. |
| RNA-seq | Separate count candidates, TPM and abundance-scaled count estimates | Follows the published nf-core/rnaseq output distinctions. Salmon estimates still require appropriate length-aware statistical import; filename recognition is not proof of count origin. |
| BLAST / custom databases | Optional native DIAMOND protein search against uploaded FASTA, with explicit sensitivity and reference scope | Executed DIAMOND 2.1.18 on exact-reference and unrelated controls. Inputs, parameters, results and executable checksums are exported. This does not change the existing NCBI/EBI workflow or assert database equivalence. |
| Pairwise | Optional composition-preserving subject-shuffle score test | Actual Biopython alignment scores for observed and shuffled sequences. Seed and null scores retained; corrected Monte Carlo P-value cannot be zero. This is an exploratory single-comparison test, not a homology probability or BLAST E-value. |
| PPI | Correct STRING JSON score handling | A live public TP53 request returned 0.999; the old code divided it by 1,000. The parser now preserves the 0–1 JSON scale and rejects unexpected values. |
| Workflow records | RO-Crate 1.1 metadata/evidence ZIP from owned experiments | Recorded evidence only; pending work is not represented as completed actions. Missing input/output payloads and provenance remain explicit. Full Workflow Run RO-Crate profile compliance is not claimed. |

## Published-method sources

- Galaxy Community, 2026: https://doi.org/10.1093/nar/gkag469 — workflow inspection, structured inputs and research-object exports. The design was independently implemented in BioNexus.
- Ewels et al., 2020: https://doi.org/10.1038/s41587-020-0439-x — community-curated Nextflow workflows. Exact RNA-seq 3.26.0 output contract: https://nf-co.re/rnaseq/3.26.0/docs/output
- Buchfink et al., 2021: https://doi.org/10.1038/s41592-021-01101-x — DIAMOND alignment. CLI source: https://github.com/bbuchfink/diamond/wiki/3.-Command-line-options
- Phipson and Smyth, 2010: https://doi.org/10.2202/1544-6115.1585 — finite random-permutation P-value calculation. The sequence-shuffle null model is BioNexus's explicit analysis choice.
- Cock et al., 2009: https://doi.org/10.1093/bioinformatics/btp163 — Biopython.
- RO-Crate specification/template: https://www.researchobject.org/ro-crate/specification/1.1/ and https://github.com/ResearchObject/ro-crate-gh-template
- STRING API contract: https://string-db.org/help/api/ — distinguishes returned evidence from input score thresholds.

## Paid-tool methodology research

The Geneious Basic publication describes a modular analysis framework and an integrated BLAST→alignment→PhyML example (https://doi.org/10.1093/bioinformatics/bts199). This supports integration patterns; it does not disclose every current Geneious Prime engine.

The Glide publication describes staged pose search, energy refinement and redocking assessment (https://doi.org/10.1021/jm0306430). Its published abstract was retrieved; the exact proprietary implementation was not recovered. Existing BioNexus Vina-based docking must retain its own scoring identity. Replacing its label with Glide would not reproduce the published engine.

Blast2GO's publication was retrieved as a primary bibliographic record (https://doi.org/10.1093/bioinformatics/bti610). The full-method lookup remains incomplete, so no Blast2GO scoring-rule reproduction is claimed.

P2Rank's full published method was accessible through its publisher (https://doi.org/10.1186/s13321-018-0285-8), including surface descriptors, random-forest ligandability and clustering. A new P2Rank integration/model execution has not been added in this branch.

## Completion loop

`requirements.json` retains all 25 original tool rows, the additional feature candidates, integration requirements and recommendations. It does not discard hard requirements because a runtime or source is unavailable.

Run the loop with the backend's Python environment and native DIAMOND configured:

```bash
BIONEXUS_DIAMOND=/absolute/path/to/diamond python scripts/verify_capability_loop.py --output /absolute/path/outside/repository
```

After each check the controller rereads the entire requirement set and writes the updated acceptance evidence. A skipped native engine check is BLOCKED, not PASSED. Unregistered acceptance checks are UNVERIFIED, not complete. Exit 1 indicates a failed delivered check; exit 2 indicates that registered checks have finished but the full original scope is incomplete. Only exit 0 permits a full-scope completion claim.

The controller runs verification; the coding agent implements gaps. It neither generates code by itself nor publishes branches. It is not a scheduled automation. The current report has `main_release_allowed: false`; this branch must not be represented as completion of the full roadmap. Some existing capabilities are implemented but have not yet been audited/registered against the stronger roadmap criteria.

## Verification checkpoint

137 selected Python regressions passed with native DIAMOND enabled; no tests were skipped. TypeScript and the production webpack build passed with telemetry disabled. All six registered acceptance checks passed. The loop retained 99 unverified capabilities from the wider scope and held the main-release flag false. Unverified does not mean absent: existing features still need acceptance registration/audit against the stronger requirements. Nextflow process monitoring was tested against the native trace format and ownership controls, not an executed live Nextflow pipeline.

## Runtime and licences

DIAMOND is a separate GPL-3.0 executable. Its exact release/archive digest is checked in the backend image. The GPL notice and corresponding source accompany it in `/usr/share/doc/diamond`. There is no commercial account requirement for the native search engine. Normal BioNexus authentication protects private queries.

The public deployment's expression storage configuration and full NGS compute remain separate known deployment requirements. Unit tests and a local production build cannot establish a live production run.
