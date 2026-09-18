# BioNexus BBS-2 fixture repository

Every directory under `fixtures/` answers the ground-truth question:
**"Where did the expected answer come from?"** No fixture may be "BioNexus vs
BioNexus". Each directory owns:

- `manifest.json` — versioned inputs + expected outputs with SHA-256 checksums.
- a `README.md` — the provenance of the expected answer (external source, pinned
  release/version, how it was derived, and how to reproduce it independently).
- a runnable comparator (`.py` or shell) that emits a persisted run record under
  `../results/<domain>/` with the BBS-2 run metadata required by
  `benchmark/BBS2_PROTOCOL.md`.

## Ground-truth provenance policy (BBS-2 §Ground truth policy, MATRIX 30)

| Domain | Expected answer comes from | Synthetic? |
|---|---|---|
| `cheminformatics/descriptor_parity` | Pinned RDKit exact descriptor computation (deterministic) | descriptor parity is deterministic reference, labelled as such |
| `cheminformatics/drug_likeness` | Published rule definitions (Lipinski/Veber/Ghose/Egan/Muegge/PAINS/Brenk) applied deterministically | deterministic rules |
| `annotation/function_go` | Held-out reviewed UniProt functional annotations (answer keys); InterPro2GO frozen mappings | ground truth external, held-out |
| `annotation/pathway_enrichment` | Pinned Reactome + g:Profiler releases; expected pathways independently queried | external |
| `evolution/phylo`, `sequence/msa` | Reference alignments/trees from trusted independent executions or curated reference datasets | external/curated |
| `ngs/germline` | GIAB truth VCF + BED (HG002), hap.py-compatible metrics | external truth set |
| `ngs/rna_seq`, `ngs/cnv`, `ngs/sv` | SEQC/MAQC-style reference material; GIAB SV/CNV pilots | external |
| `docking/redock_panel` | Crystallographic ligand poses from co-crystal complexes (symmetry-aware heavy-atom RMSD) | external |
| `blast/queries` | Expected accessions from a pinned database release; retrieval date frozen | external |
| `ai/adversarial` | Deliberately injected unsupported citations / wrong identifiers / fabricated numbers / reversed interpretations / source mismatches | synthetic (adversarial) |
| `ai/prompts` | Structured fact sets attached to real BioNexus analysis outputs; expert-reviewed answer keys for biology | synthetic wrappers over real outputs |

## Status semantics (matches BBS-2)

- `defined` — spec exists.
- `fixture-ready` — inputs + expected outputs committed with checksums.
- `executable` — BioNexus runs the benchmark end to end.
- `validated` — a recorded run satisfies the predeclared acceptance rule.
- `regression` — mandatory in CI, blocks release on failure.

A fixture directory that is committed with expected outputs is `fixture-ready`.
A run record under `results/` that meets its acceptance rule promotes the domain
to `validated` — and only `results/` records (never the fixture's own intent) may
be cited as evidence.

## Aggregate manifest

`manifests/fixtures_manifest.json` lists every committed file with its SHA-256.
`benchmark/verify_fixtures.py` validates it and fails CI on any drift.