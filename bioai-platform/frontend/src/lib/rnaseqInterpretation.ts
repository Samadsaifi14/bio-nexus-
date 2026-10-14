import type { RnaSeqExpressionResult } from './rnaseqExpressionApi';

export type RnaSeqEvidenceStatement = { title: string; text: string; artifacts: string[] };
export type RnaSeqInterpretation = { title: string; statements: RnaSeqEvidenceStatement[]; caveats: string[] };

function exact(value: unknown): string {
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : 'not reported';
}
function text(value: unknown): string { return typeof value === 'string' && value.trim() ? value : 'not reported'; }
function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : typeof value === 'string' ? [value] : [];
}

/** Explain recorded output; do not infer biology or recompute statistics. */
export function explainRnaSeqResult(result: RnaSeqExpressionResult): RnaSeqInterpretation {
  if (result.state !== 'SUCCEEDED' || !result.summary) return {
    title: 'Interpretation awaits a completed analysis', statements: [],
    caveats: ['No completed statistical result is available. No differential-expression conclusion was generated.'],
  };
  const s = result.summary;
  const statements: RnaSeqEvidenceStatement[] = [
    { title: 'Comparison and direction', text: 'The model compares ' + text(s.test_level) + ' with ' + text(s.reference_level) +
      ' as reference. Positive log2 fold changes indicate higher expression in the test group; negative values indicate lower expression. The recorded design is ' + text(s.design) + '.',
      artifacts: ['analysis_summary.json', 'design_audit.json'] },
    { title: 'Counts and normalization', text: 'The run reports ' + exact(s.samples) + ' samples, ' + exact(s.genes_input) +
      ' input genes and ' + exact(s.genes_kept) + ' genes retained for testing. Normalization was ' +
      (s.normalization_method === 'tximport_length_offsets' ? 'tximport with gene-length offsets' :
       s.normalization_method === 'median_of_ratios' ? 'DESeq2 median of ratios' : 'not recorded in this saved summary') +
      '. Normalized counts and transformed plotting values are separate from the raw input counts.',
      artifacts: ['analysis_summary.json', 'normalized_counts.tsv', 'size_factors.tsv'] },
    { title: 'Differential expression', text: s.significant === 0 ?
      'No genes met both declared cutoffs: adjusted p-value < ' + exact(s.alpha) + ' and absolute log2 fold change > ' + exact(s.lfc_threshold) +
      '. This does not establish that the conditions have no biological differences.' :
      'The saved result reports ' + exact(s.significant) + ' genes meeting adjusted p-value < ' + exact(s.alpha) +
      ' and absolute log2 fold change > ' + exact(s.lfc_threshold) + ': ' + exact(s.up) + ' higher and ' + exact(s.down) +
      ' lower in the test group. These are statistical calls under the recorded design, not confirmed mechanisms.',
      artifacts: ['analysis_summary.json', 'deseq2_all_results.tsv', 'deseq2_significant.tsv'] },
    { title: 'PCA and quality control', text: 'PCA summarizes differences among samples on variance-stabilized data. The recorded variance percentages are PC1: ' +
      exact(s.pca_percent_variance?.PC1) + ' and PC2: ' + exact(s.pca_percent_variance?.PC2) +
      '. These axes alone do not establish treatment effects or causality. Inspect outliers, sample identities and batch metadata alongside the distance heatmap.',
      artifacts: ['pca_coordinates.tsv', 'sample_distance_matrix.tsv', 'design_audit.json'] },
  ];
  if (s.expression_heatmap_generated) statements.push({
    title: 'Heatmap meaning',
    text: s.expression_heatmap_basis === 'significant_DE_genes' ?
      'The heatmap displays selected significant genes using row-standardized VST values. It shows within-gene sample patterns rather than absolute abundance differences between genes.' :
      'The heatmap is an exploratory view of variable genes. Its rows must not be described as significant differential genes.',
    artifacts: ['heatmap_gene_selection.tsv', 'heatmap_matrix_zscore.tsv'],
  });
  const e = s.enrichment;
  if (e) {
    const meaning = e.status === 'SUCCEEDED' ? 'Significant gene-set tests were reported. Enrichment indicates association with annotations, not activation, inhibition or a causal mechanism.' :
      e.status === 'NO_SIGNIFICANT_TERMS' ? 'No gene-set tests passed the declared correction threshold. A null result is valid and does not prove absence of biological activity.' :
      e.status === 'UNRESOLVED_ESTIMATES' ? 'The requested enrichment estimates are unresolved; this is not evidence of no enrichment.' :
      'Enrichment status is ' + text(e.status) + '. Do not treat unavailable annotation or untestable gene sets as negative biological findings.';
    statements.push({ title: 'Functional enrichment', text: meaning + ' Recorded method: ' + text(e.method) +
      '. ' + (e.interpretation_note || ''), artifacts: ['go_enrichment_summary.json', 'go_enrichment_all.tsv', 'go_gene_mapping.tsv', 'go_background.tsv'] });
  }
  const caveats = [
    ...strings(s.design_warnings),
    ...(e?.coverage_warning ? [e.coverage_warning] : []),
    'An AI explanation or successful computation does not independently validate sample labels, biological independence, gene function or clinical relevance.',
    'This explanation reads the saved summary. Inspect and download the referenced numerical evidence before drawing biological conclusions.',
  ];
  if (s.design_full_rank !== true) caveats.unshift('Model identifiability is not confirmed by this saved summary; review the design audit before interpreting condition effects.');
  return { title: 'Evidence-linked RNA-seq interpretation', statements, caveats: [...new Set(caveats)] };
}
