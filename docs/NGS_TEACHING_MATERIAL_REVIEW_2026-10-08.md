# NGS teaching-material review, 8 October 2026

The supplied materials were compared with the current implementation. Existing statistical code was retained. Lecture examples and suggested thresholds are teaching guidance, not validation evidence or universally applicable production defaults.

## What changed

- Preview allele trimming preserves the indel anchoring base, updates the 1-based position after prefix trimming, and keeps every ALT allele in its original order. It does not split genotypes or discard alternative alleles. Invalid or unsupported records stay in the report with explicit QC failures. Indels are flagged as requiring reference-based left alignment; this Python stage does not claim to perform it.
- Missing GQ is explicitly unevaluated rather than assigned 99. Nonfinite, negative, Boolean or nonnumeric GQ fails QC. Genotype quality remains distinct from site QUAL in exported VCF. Read allele fractions use the explicitly described VAF annotation, separate from cohort allele frequency. A scalar VAF is not assigned to a multiallelic record. Caller agreement alone cannot generate a FILTER=PASS label.
- Declared small-RNA libraries and small-RNA input/reference hints are detected before generic RNA hints. The API and stage builder prevent their routing into bulk-RNA/DNA preview pipelines and explain the need for kit-specific adapter/UMI processing, length-distribution QC, short-read mapping policy and versioned annotations. GEO miRNA-Seq library strategies likewise block the automatic gene-count importer. A dedicated small-RNA execution pipeline is not implemented by this change.
- Regression tests verify reconstructed haplotype equivalence, ALT ordering and metadata preservation, trimming idempotence, GQ/QUAL separation, invalid records and small-RNA API guidance. The new contracts run in backend CI.

## Source-to-implementation comparison

| Material | Relevant content | Decision and implementation |
| --- | --- | --- |
| Lecture 8, Transfer and Computing Skills | Checksums, archives, complete input, compute resources and reproducibility | Already covered by bounded ingestion, checksums, explicit preview sampling, versioned production launch contracts and execution provenance. Leave these mechanisms unchanged. |
| Lecture 9, Principles of RNA-seq | Gene counts, composition bias, sample comparison, statistical inference | Existing DESeq2 median-of-ratios normalization and expression figures retained. Gene-count workflows cannot discover unannotated transcripts, fusions or RNA variants from counts alone. |
| Practical DESeq2 Normalization and DEG | Sample metadata, prefiltering, size factors, VST/PCA, dispersions, shrinkage and DEG tables | Existing R execution, integer-count validation, design checks, plots and exports retained. The current shrinkage implementation records its method and failure status. |
| Lecture 10, Experimental Design | Biological units, technical replication, batch confounding, factorial designs | Existing unit/replication, covariate and design-rank checks retained. Current count analysis estimates a two-level condition contrast with additive covariates. Factorial interactions are not implemented and are not implied by this review. |
| Cer SALS input | 22,085 genes, 18 samples, 8 healthy and 10 SALS | Already used for the teaching workflow. The bundled 221-gene fixture remains a software regression subset. No additional biological result was generated in this review. |
| Lecture 12, Discovery and Small RNA, slides 10-19, 21-25 | Mandatory assay-specific trimming, length QC, multimapping, catalogue provenance, normalization and target-prediction limitations | Added dedicated assay detection and actionable refusal of incompatible bulk processing. Do not infer miRNA targets from gene GO enrichment or claim small-RNA execution. No automatic adapter sequence, universal length window or database release is guessed. |
| Lecture 13, Genotyping and Variation Discovery, especially read groups and BQSR | Sorted/indexed alignments, sample/library read groups, marked duplicates, known-sites recalibration and removal of legacy realignment | Production Sarek contract and reference/provenance requirements already exist. Leave pinned workflow unchanged. The Python BAM stage remains a simplified preview, not executed GATK preprocessing. No legacy IndelRealigner command is added. |
| Lecture 14, SNV/Indel Calling and VCF, slides 9, 15-19 | Anchored alleles and coordinates, multiallelic semantics, GQ versus QUAL, separate filtering and matched-reference truth evaluation | Fixed preview allele/QC/export semantics. Existing Sarek joint-germline planning and GIAB/GA4GH evidence boundaries retained. Trio de novo calling, RNA-variant calling, VQSR and somatic filtering are not newly implemented. |
| GATK presentation | Reference indexing, read groups, BQSR known sites, GVCF/joint genotyping, filtering and alternate platforms | Matches existing production-planning requirements. Retained their versions and external execution boundary. Lecture commands are not labelled as executed by BioNexus. |
| Both Genetic Algorithm PDFs | Candidate representations, objective/fitness, selection, crossover, mutation and optimization examples | Reviewed but not added to NGS calling or thresholds. Stochastic optimization needs a prespecified objective and independent validation. Adding it merely because it models genetics would not improve scientific validity. |

## Duplicate and source identity

The two Lecture 14 uploads have identical SHA-256 hashes and count as one source. No uploaded slides or PDFs were modified or copied into the repository.

| Uploaded source | SHA-256 |
| --- | --- |
| 01-Lecture9_Principles_of_RNA_Seq.pptx | `e0309c1d3cbb8ea0c77914409b261372f1d1988f29690db8e150b0d99d61a735` |
| 02-Lecture8_Transfer_Computing_Skills.pptx | `8c8dc8a629bc882346e240901fb7e3ef2ab6efcc6776e97872abb1a3ca29e88e` |
| 03-Practical_DESeq2_Normalization_DEG.pptx | `7c950441f5eca3c912ef13eb25a872547a801d432c3e1d4c90eebab10e02c27d` |
| 04-Lecture10_RNA_Seq_Experimental_Design.pptx | `eb5d1774475bf2f19330e8480741bdbf7f4965fb50688f59e0df23584d0bb421` |
| 05-Cer_SALS_file_for_Dseq_input.txt | `b7a9736672a6cebfdeea78dd151f5c764b058537cac09aeb0256cbfb7123dc08` |
| GATK_ppt.pdf | `9a83f4e57acad9d9c7d58f99d21450cfa6384a6084b12512a7559a8269c36b04` |
| Genetic_Algorithm_261007_223018.pdf | `1013d11c932d12489a4e3c3b9959cfa0a3a17c1a0ae867ab9b2f859263059977` |
| Genetic_Algorithm_BiologicalConcepts_261007_222948.pdf | `15bb5199925159669a54771937b9cef45ede8965ff12fd3228c95470765fa620` |
| Lecture12_Discovery_and_SmallRNA_Seq.pptx | `baf341c5228ef70e5560fd31a2792408f8b62f1c6f9788152a6cd21b2df1d491` |
| Lecture13_Genotyping_Variation_Discovery.pptx | `36f8dbeb80e7b225b0f791dff2348b0506d98c2521f84a94b6dfe2dd70fd6c76` |
| Lecture14_SNV_Indel_Calling_VCF (1)(1).pptx | `753c0eca88e329d7276ce3bf1d622a7b65aefdf78830e6a8a94f17c36fba604c` |
| Lecture14_SNV_Indel_Calling_VCF (1).pptx | `753c0eca88e329d7276ce3bf1d622a7b65aefdf78830e6a8a94f17c36fba604c` |

## Primary technical references

- [VCF format specification](https://samtools.github.io/hts-specs/VCFv4.3.pdf): anchoring, coordinates, QUAL, FILTER and genotype fields.
- [nf-core/smrnaseq documentation](https://nf-co.re/smrnaseq/2.4.1/docs/usage/): dedicated small-RNA workflow, protocol-specific adapters and UMI handling. This is a reference link, not an executed or added BioNexus workflow.
- [GATK SplitNCigarReads](https://gatk.broadinstitute.org/hc/en-us/articles/30332077175963-SplitNCigarReads): RNA-variant preprocessing differs from expression quantification and DNA calling.

No scientific-accuracy or clinical-validation claim follows from passing software tests.
