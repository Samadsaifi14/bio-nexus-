# BLAST parser-fidelity reference bundle (SEQ-BLAST extension)

## What this is

A reference-parser benchmark. The object under test is
`bioai-platform/backend/app/integrations/ncbi/parser.py::parse_blast_xml` —
the normalizer that turns raw NCBI `BlastOutput` XML into the structured hit
list the API and pipeline serve. It compares every parsed field against the
frozen reference with explicit tolerance rules, and verifies download parity
(JSON + CSV serialization must preserve every parsed value losslessly).

## Files

| File | Purpose |
|---|---|
| `synthetic_structure.xml` | **Synthetic structural regression fixture.** Contrived identifiers on purpose; NCBI DTD `BlastOutput` schema. Exercises the comparison machinery offline; never claims to be ground truth. |
| `reference.json` | Independent literal extraction of the XML (first HSP per hit) + source shasum. `origin` field records `synthetic-structural` or `ncbi-live`. |
| `record_reference.py` | Regenerates `reference.json`. `--live` submits a real `blastp` to NCBI `Blast.cgi` (Put/Get, `FORMAT_TYPE=XML`), saves the genuine namespaceless NCBI `BlastOutput` XML as `ncbi_live_<ts>.xml`, marks `origin: ncbi-live` with RID capture metadata, then extracts the reference. |
| `run_blast_parser_fidelity.py` | Offline CI-safe runner. Verifies the XML shasum, runs `parse_blast_xml`, compares top-5 hits field-by-field under tolerance rules, runs download parity, writes `benchmark/results/sequence/blast_parser/latest.json`. Exit 0 = PASS, 1 = FAIL, 2 = requires_external. |

## Tolerance rules (documented)

- **exact (string):** `accession`, `id`, `description`, `organism`,
  `evalue_raw`, `query_alignment`, `hit_alignment`, `midline`
- **exact (int):** `length`, `score`, `identity`, `positive`, `gaps`,
  `alignment_length`, `query_from`, `query_to`, `hit_from`, `hit_to`,
  `query_length`
- **float:** `bit_score` absolute ≤ 0.001; `evalue` relative ≤ 1e-9 when
  ref ≠ 0 else absolute ≤ 1e-300; `identity_pct` absolute ≤ 0.11 (covers the
  1-decimal rounding)

## Status: live NCBI capture pending

The genuine NCBI reference requires a completed NCBI BLAST queue job. During
capture attempts NCBI's `swissprot` queue was repeatedly not READY within a
bounded poll window (RID assigned, queue delay minutes+), so no `ncbi-live`
bundle is committed yet. Until one is:

- the committed bundle is `synthetic-structural` only, and
- no 'validated vs NCBI' wording may be used for the parser.

When a live capture succeeds (`python record_reference.py --live
--budget 600`), commit the saved `ncbi_live_*.xml` + regenerated
`reference.json` and update this paragraph.

## Running

```bash
python record_reference.py                     # regenerate reference.json (offline)
python run_blast_parser_fidelity.py            # PASS/FAIL -> results/sequence/blast_parser/latest.json
```