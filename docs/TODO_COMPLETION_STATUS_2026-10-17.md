# BioNexus remaining work — evidence ledger

## Repairs in this continuation

- PPI: preserve native STRING API confidence; remove the erroneous /1000 conversion. Reject malformed source scores rather than fabricate zero. Plain Python defaults and FastAPI query constraints both work.
- ADMET: distinguish chemical hydrogen-bond acceptors from Lipinski N+O count; retain the named method for each. Aspirin: HBA=3, N+O=4. Quaternary nitrogen is not automatically an acceptor.
- Reference reproducibility: pin RDKit 2026.9.1; retain the 2022.09.5 expected reference untouched and add a versioned 2026.09.1 reference. Ten changes were captured in executed CI job 117461641392 (run 39055198517), including acceptor counts, ring counts and organotin SMILES. Same-version descriptor determinism is not pharmacology or clinical validation.
- Dashboard regression: verify authenticated ownership, tenant-separated storage, merged catalog/owned datasets and cross-tenant isolation.
- De novo regression: use a genuinely completed zero-hit BLAST fixture. Provider failure remains distinct and covered by the false-de-novo guard suite.
- Earlier repairs retained: statistical plotting/missingness/CSV; per-job worker retry budgets; correct row-vector Kabsch alignment; signed authentication smoke fixtures; interpretation numeric grounding and streaming.

## Completion conditions still open

The full backend suite must finish at the release commit. Its previous complete run had 1,456 pass / 53 fail / 28 skip; do not reuse that count as a result for this commit. Focused tests and frontend builds cannot certify the whole product.

External BLAST/function/structure/MD integrations need observed provider outputs and sufficient runtime, not just mocks. Multi-complex docking, production-scale NGS and long MD need their declared external tools/data/compute and archived acceptance records. Reference determinism does not replace these.

The source roadmap in docs/SCIENTIFIC_ROADMAP_STATUS.md and benchmark/VERIFICATION_MATRIX.json retains partially implemented and validation-pending items. This ledger does not mark them complete.

The execution environment is unavailable. The attached local lecture slides and count file cannot be read through shell/Python; browser and authenticated end-to-end verification remain blocked. No claim of fresh slide review, full 25-feature parity or completed external validation is made.
