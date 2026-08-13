'use client';

import { usePathname } from 'next/navigation';
import { JsonLd } from './JsonLd';
import { SITE_URL } from '@/lib/seo';

const SEGMENT_LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  analyze: 'Analyze',
  wizard: 'Wizard',
  jobs: 'Jobs',
  history: 'History',
  retrieve: 'Retrieve',
  results: 'Results',
  report: 'Report',
  settings: 'Settings',
  learn: 'Learn',
  blast: 'BLAST Search',
  alignment: 'Sequence Alignment',
  pairwise: 'Pairwise Alignment',
  dotplot: 'Dot Plot',
  motif: 'Motif Scanner',
  domains: 'Domain Analysis',
  phylo: 'Phylogeny',
  structure: 'Structure Prediction',
  interactions: 'Protein Interactions',
  docking: 'Molecular Docking',
  md: 'Molecular Dynamics',
  admet: 'ADMET Prediction',
  primers: 'Primer Design',
  sequencing: 'Sequencing',
  function: 'Function Prediction',
  pathway: 'Pathway Analysis',
  compare: 'Sequence Comparison',
  sequences: 'Sequence Utilities',
  tools: 'Format Converter',
  uniprot: 'UniProt Lookup',
};

const ID_LIKE = /^[a-f0-9]{8,}$/i;

function humanize(segment: string): string {
  return segment
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function BreadcrumbSchema() {
  const pathname = usePathname();
  const parts = pathname.split('/').filter(Boolean);

  const items: { name: string; item?: string }[] = [
    { name: 'Home', item: `${SITE_URL}/` },
  ];
  let acc = '';
  for (const part of parts) {
    acc += `/${part}`;
    if (ID_LIKE.test(part) && items.length > 1) continue;
    items.push({ name: SEGMENT_LABELS[part] ?? humanize(part), item: `${SITE_URL}${acc}` });
  }

  const last = items[items.length - 1];
  if (last) delete last.item;

  return (
    <JsonLd
      data={{
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: items.map((it, i) => ({
          '@type': 'ListItem',
          position: i + 1,
          name: it.name,
          ...(it.item ? { item: it.item } : {}),
        })),
      }}
    />
  );
}
