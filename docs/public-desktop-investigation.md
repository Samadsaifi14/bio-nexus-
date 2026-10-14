# Public applications, then desktop packages

This pass followed the requested order: publicly accessible application artifacts first, official desktop distributions second. Exact URLs, SHA-256 identities and REA Evidence IDs are recorded in [rea-public-desktop-evidence.json](rea-public-desktop-evidence.json). No vendor code, assets or installers are redistributed in this repository.

## Public applications

Actual shipped JavaScript was acquired from Galaxy, Terra, Seqera, Latch, Basepair, DNAnexus and OmicsBox web. REA's safe file inventory succeeded. DNAnexus coverage is bootstrap-only, and other applications retain lazy-module gaps. Benchling's inspected homepage was marketing material and was excluded from laboratory-application conclusions. The selected Partek page returned HTTP 502.

Galaxy's downloaded bundle contains collection/list identities and dataset-collection routing. Terra's selected loader contains workspace/submission request construction; Seqera contains compute/launchpad/workspace identities. These are bounded ordinary static observations, not observed backend behavior. REA semantic parsing remains blocked by its process-ownership prerequisite: a child `ps` invocation reports `fatal library error, lookup self`. The safeguard was retained. Successful artifact inventory does not mean successful semantic reconstruction.

## Desktop packages

| Package | Actual acquisition and inspection | Boundary |
|---|---|---|
| Geneious Prime 2026.1.2 | Official 426,655,319-byte Linux installer downloaded. Installer wrapper is unsupported by REA; embedded ZIP payload was identified by central-directory byte offsets without running it. REA inventoried extracted alignment-column and primer plugin archives. | Class/member identities only. No licensed analysis, Java implementation recovery or algorithm equivalence established. |
| OmicsBox 4.1.3 | Official 637,416,543-byte Linux installer downloaded; SHA-256 matched the value published on the vendor download page. Embedded package was read statically and REA inventoried its statistics API archive. | No subscription activation, cloud analysis, ontology inference or statistical behavior reconstructed. |
| BIOVIA Discovery Studio 2025 Visualizer | Official publicly linked Windows installer downloaded. REA's static PE-resource inspection succeeded. | Installer resources only; the modeling application and docking algorithms were not executed or reconstructed. |
| CLC Genomics Workbench | Official direct-download page was requested and returned HTTP 403 in this environment. | No CLC package inspected. |
| SnapGene | Official download access requires a registration code/account; trial page requests an email. | No account was created or trial request submitted; no desktop package acquired. |
| MOE / Schrödinger | Official download pages require a download code/license or account. | No gated artifacts acquired; no license bypass. |

Sources: [Geneious installers](https://www.geneious.com/download-previous-versions), [OmicsBox downloads](https://www.biobam.com/download-omicsbox/), [BIOVIA public download links](https://discover.3ds.com/discovery-studio-visualizer-download-thank-you), [CLC direct downloads](https://digitalinsights.qiagen.com/products/clc-genomics-workbench-direct-download/), [SnapGene downloads](https://www.snapgene.com/support/downloads), [MOE access](https://www.chemcomp.com/en/Download_Request.htm), [Schrödinger downloads](https://www.schrodinger.com/release-download/).

## Delivered BioNexus capabilities

- **Protein collection workflows:** a validated recipe can queue 1–10 canonical protein FASTA records. Validation finishes before queue writes. Each owned job stores collection/member/input identities. Stable submission UUIDs and deterministic job primary keys reconcile retries, including partial submissions and concurrent insert conflicts. Reusing an ID with changed input or recipe is rejected. Completion and failure preserve submission metadata without reusing old scientific results.
- **Alignment column filtering:** the alignment page accepts aligned DNA/RNA/protein FASTA. Default filtering removes all-gap columns; optional any-gap/percentage policies disclose residue deletion. Exports include trimmed FASTA, original-to-retained column mapping, input/output hashes and deletion counts. Filtering does not realign sequences or replace prior results.

These are independent implementations of bounded feature mechanisms identified in the artifacts. They are not copied proprietary code or proven vendor-behavior replicas. Geneious's archive explicitly names all-gap, any-gap and percentage-gap option classes; their presence does not establish exact thresholds or implementation details, so BioNexus policies are stated independently.

## Verification and operational limits

112 selected tests passed across collection validation/retries/finalization, workflow replay/manifests, alignment filtering, sequence tools, restriction maps and annotated exports. Frontend TypeScript and the local production build passed. An HTTP smoke check of the locally served alignment page confirmed that the filtering panel was rendered. No authenticated competitor execution, live Supabase queue execution or browser interaction QA is claimed.

Deterministic IDs prevent duplicate jobs for the same owner/submission/member. Daily-capacity checks are not an atomic reservation across distinct concurrent requests; deployment-scale quota enforcement still requires database coordination. Existing migrations are sufficient for stored collection metadata; the matching backend must be deployed for the new endpoints. Full competitor reconstruction and commercial parity remain incomplete.

## Runtime follow-up

The original local process-ownership failure was subsequently resolved in a compatible VM. [Verified runtime evidence](rea-compatible-environment/README.md) separates successful parsing from retained static unknowns and the remaining Galaxy semantic heap limit. Earlier blocked records above describe the initial local pass.
