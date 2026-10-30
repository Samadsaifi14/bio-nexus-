import type { JobStatus } from '@/types/pipeline';

/**
 * Analysis-tool jobs share the `jobs` table with the BLAST pipeline but have no
 * BLAST/UniProt context. Map each tool key to a readable label and the page that
 * can run it again.
 */
export const TOOL_META: Record<string, { label: string; href?: string }> = {
  phylo: { label: 'Phylogenetic tree', href: '/analyze/phylo' },
  md: { label: 'Molecular dynamics', href: '/analyze/md' },
  md_v2: { label: 'Staged molecular dynamics', href: '/analyze/md-v2' },
  docking: { label: 'Molecular docking', href: '/analyze/docking' },
  sequencing: { label: 'Sequencing QC', href: '/analyze/sequencing' },
  ngs: { label: 'NGS analysis', href: '/analyze/ngs' },
  function_predict: { label: 'Protein function prediction', href: '/analyze/function' },
  structure_predict: { label: 'Structure prediction', href: '/analyze/predict-structure' },
  structure_prep: { label: 'Structure preparation', href: '/analyze/structure-prep' },
  castp: { label: 'Pocket & cavity analysis', href: '/analyze/castp' },
  admet: { label: 'ADMET descriptors', href: '/analyze/admet' },
  protox: { label: 'ProTox toxicity prediction', href: '/analyze/admet' },
  pairwise: { label: 'Pairwise alignment', href: '/analyze/pairwise' },
  msa: { label: 'Multiple sequence alignment', href: '/analyze/alignment' },
  seq_analysis: { label: 'Sequence analysis', href: '/analyze/sequences' },
  motif_scan: { label: 'Motif scan', href: '/analyze/motif' },
  motif_library: { label: 'Motif library scan', href: '/analyze/motif' },
  dotplot: { label: 'Dot plot', href: '/analyze/dotplot' },
  prosite_scan: { label: 'PROSITE scan', href: '/analyze/domains' },
  primer_design: { label: 'Primer design', href: '/analyze/primers' },
  primer_qc: { label: 'Primer quality control', href: '/analyze/primers' },
  pathway_enrichment: { label: 'Pathway enrichment', href: '/analyze/pathway' },
};

/** Tool metadata for a tool-job row, or `null` for the BLAST pipeline. */
export function toolMetaFor(job: JobStatus): { label: string; href?: string } | null {
  const key = (job.tool || job.pipeline_type || '').trim();
  return key in TOOL_META ? TOOL_META[key] : null;
}

/** Human label for any job row (pipeline steps keep their own labels). */
export function toolLabel(job: JobStatus): string | null {
  const key = (job.tool || job.pipeline_type || '').trim();
  return TOOL_META[key]?.label ?? null;
}
