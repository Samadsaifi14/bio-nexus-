'use client';

import { useState } from 'react';
import { BackButton, ClaySegmented, PageHeader } from '@/components/ui';
import { ReferenceComparisonWorkbench } from '@/components/results/ReferenceComparisonWorkbench';

const DOMAINS = [
  ['blast', 'BLAST'],
  ['msa', 'MSA'],
  ['phylo', 'Phylogeny'],
  ['primers', 'Primers'],
  ['pathway', 'Pathways'],
  ['rnaseq', 'RNA-seq'],
  ['ngs', 'WGS/WES'],
  ['docking', 'Docking'],
  ['md', 'MD'],
  ['admet', 'RDKit / ADMET'],
  ['domains', 'Domains'],
  ['motif', 'Motifs'],
  ['function', 'Function evidence'],
  ['interactions', 'Interactions'],
  ['structure', 'Structure'],
  ['castp', 'Pockets'],
  ['uniprot', 'UniProt'],
  ['pairwise', 'Pairwise alignment'],
] as const;

export default function ValidationPage() {
  const [analysisType, setAnalysisType] = useState<string>('blast');
  return (
    <div className="max-w-6xl">
      <BackButton />
      <PageHeader
        title="Scientific Reference Comparison"
        subtitle="Compare BioNexus outputs against independent accepted tools or truth sets using domain-specific concordance metrics."
      />

      <div className="mb-5 data-card p-4">
        <p className="mb-3 text-xs text-text-muted">Choose the analysis domain. A reference source is suggested for each domain; use the same input and scientific settings whenever exact concordance is the goal.</p>
        <ClaySegmented
          options={DOMAINS.map(([value, label]) => ({ value, label }))}
          value={analysisType}
          onChange={setAnalysisType}
          className="flex flex-wrap"
        />
      </div>

      <ReferenceComparisonWorkbench key={analysisType} analysisType={analysisType} />
    </div>
  );
}
