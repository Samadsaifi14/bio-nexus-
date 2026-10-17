# Remaining-repair verification — 18 October 2026 (Asia/Kolkata)

## Executed evidence

Source commit 80ed85d6f4f27406bd5250001ab72982ece03c8e:
- Focused statistics, authentication, ADMET, PPI, structure and interpretation regressions: **148 passed**.
- Native local BLAST+ routing and integrity tests: **7 passed**, using actual executables, not mocked alignments.
- Production BlastTool accession-recovery panel: **8/8 recovered** within the predeclared top five; both essential controls passed.
- Reference: UniProt **2026_03**, **575,748** canonical Swiss-Prot sequences.
- FASTA SHA-256: `1372f18e218d761027616bf17479bcf450b30314fc0a8095fcb0e97e85d6ecf9`.
- Full native record: `benchmark/results/sequence/local_blast/2026-10-17-uniprot-2026_03.json`.
- CI run: https://github.com/Samadsaifi14/bio-nexus-/actions/runs/39064996209
- Retained artifact: `local-blast-reference-evidence` (query FASTA, XML, manifest and verdict).

These are same-reference positive controls of accession recovery/routing, not experimental or novel-sequence accuracy validation. Reference corruption fails closed. Local Swiss-Prot never substitutes silently for nr, comprehensive UniProt or nucleotide databases.

## Closed repair items

1. ADMET audit conventions now assert chemical acceptors and Lipinski N+O counts separately, including seeded native-RDKit comparisons.
2. Polling contract recognises STUCK as an unsuccessful terminal service state.
3. Protein searches against Swiss-Prot have a locally executed route independent of remote provider queues.
4. The production image provisions and fingerprints the complete reference; run results retain native HSP evidence and its identity.
5. Frontend build, descriptor parity and scientific foundation checks passed for the executed source revision.

## Still not certified complete

The previous full audit (8c744a5) had 1,528 pass, 9 fail and 31 skip: two ADMET convention mismatches, three STUCK enumeration mismatches and four live BLAST issues/timeouts. The code repair and successful local controls do not imply that the remote NCBI/EBI service probes passed; the current full audit must report its actual outcome.

The broader scientific roadmap still has partial implementations and unexecuted external-validation items. No claim of all-25-tool parity or completed scientific validation is made.

The execution workspace remains unavailable. Uploaded lecture slides/count-file copies and authenticated browser workflows could not be inspected in this continuation. GitHub CI executes repository code; it does not read those inaccessible attachments.
