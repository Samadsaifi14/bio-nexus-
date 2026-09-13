export type ScientificComparisonSample = {
  label: string;
  description: string;
  bionexus: Record<string, unknown>;
  reference: Record<string, unknown>;
  referenceTool: string;
  referenceVersion: string;
  referenceDatabase: string;
  topN?: number;
};

/**
 * Deterministic UI/regression fixtures for the Scientific Reference Comparison workspace.
 *
 * IMPORTANT: these are not external validation datasets and must never be cited as evidence
 * that BioNexus agrees with the named tool. They exist so the comparison UI can be exercised
 * without requiring users to collect an external result first.
 */
export const SCIENTIFIC_COMPARISON_SAMPLES: Record<string, ScientificComparisonSample> = {
  blast: {
    label: 'Protein BLAST concordance demo',
    description: 'Ranked-hit fixture with matching accessions and small score differences to demonstrate hit overlap, rank profiles and correlation metrics.',
    referenceTool: 'NCBI BLAST-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'DEMO Swiss-Prot-like reference',
    topN: 5,
    bionexus: {
      hits: [
        { accession: 'P68871', identity_pct: 100, query_coverage_pct: 100, bit_score: 286.1, evalue: 2e-98 },
        { accession: 'P02042', identity_pct: 92.3, query_coverage_pct: 100, bit_score: 263.8, evalue: 4e-89 },
        { accession: 'P02100', identity_pct: 88.6, query_coverage_pct: 98.7, bit_score: 247.4, evalue: 7e-83 },
        { accession: 'P01966', identity_pct: 84.9, query_coverage_pct: 97.1, bit_score: 231.7, evalue: 2e-76 },
        { accession: 'P02070', identity_pct: 81.5, query_coverage_pct: 96.4, bit_score: 219.2, evalue: 5e-71 },
      ],
    },
    reference: {
      hits: [
        { accession: 'P68871', identity_pct: 100, query_coverage_pct: 100, bit_score: 286.0, evalue: 2e-98 },
        { accession: 'P02042', identity_pct: 92.3, query_coverage_pct: 100, bit_score: 263.5, evalue: 5e-89 },
        { accession: 'P02100', identity_pct: 88.6, query_coverage_pct: 98.7, bit_score: 247.0, evalue: 8e-83 },
        { accession: 'P01966', identity_pct: 84.9, query_coverage_pct: 97.1, bit_score: 231.2, evalue: 3e-76 },
        { accession: 'P02070', identity_pct: 81.5, query_coverage_pct: 96.4, bit_score: 218.9, evalue: 6e-71 },
      ],
    },
  },
  msa: {
    label: 'Clustal-style alignment demo',
    description: 'Three-sequence aligned-FASTA fixture for sequence-set, checksum, pairwise-identity and conservation-profile comparison.',
    referenceTool: 'EMBL-EBI Clustal Omega-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'Same three demo sequences',
    bionexus: {
      aln_fasta: '>seqA\nMKTAYIAKQRQISFVKSHFSRQDILDLW\n>seqB\nMKTAYIAKQRQISFVKSHFSRQNILDLW\n>seqC\nMKTAYIAKQKQISFVKSHFSRQDILDLW',
    },
    reference: {
      aln_fasta: '>seqA\nMKTAYIAKQRQISFVKSHFSRQDILDLW\n>seqB\nMKTAYIAKQRQISFVKSHFSRQNILDLW\n>seqC\nMKTAYIAKQKQISFVKSHFSRQDILDLW',
    },
  },
  phylo: {
    label: 'Tree-topology demo',
    description: 'Same leaf set and topology with slightly different branch lengths; topology metrics should remain concordant.',
    referenceTool: 'IQ-TREE-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'Same aligned demo sequences',
    bionexus: { newick: '((seqA:0.10,seqB:0.12):0.08,(seqC:0.09,seqD:0.11):0.07);' },
    reference: { newick: '((seqA:0.11,seqB:0.13):0.08,(seqC:0.10,seqD:0.12):0.06);' },
  },
  primers: {
    label: 'Primer3 candidate demo',
    description: 'Two primer-pair candidates with small Tm/GC/product-size differences.',
    referenceTool: 'Primer3-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'Same DNA template and design settings',
    bionexus: {
      pairs: [
        { left_seq: 'AGCTGACCTGATCGTACGTA', right_seq: 'TGCATCAGGTCCTGATGCTA', left_tm: 60.2, right_tm: 60.6, left_gc: 50.0, right_gc: 50.0, product_size: 218 },
        { left_seq: 'GACCTGATCGTACGTAGGCA', right_seq: 'CATCAGGTCCTGATGCTAAC', left_tm: 61.0, right_tm: 60.8, left_gc: 55.0, right_gc: 50.0, product_size: 241 },
      ],
    },
    reference: {
      pairs: [
        { left_seq: 'AGCTGACCTGATCGTACGTA', right_seq: 'TGCATCAGGTCCTGATGCTA', left_tm: 60.1, right_tm: 60.5, left_gc: 50.0, right_gc: 50.0, product_size: 218 },
        { left_seq: 'GACCTGATCGTACGTAGGCA', right_seq: 'CATCAGGTCCTGATGCTAAC', left_tm: 60.9, right_tm: 60.7, left_gc: 55.0, right_gc: 50.0, product_size: 241 },
      ],
    },
  },
  pathway: {
    label: 'Reactome enrichment demo',
    description: 'Stable-ID, FDR and gene-ratio comparison across three pathway rows.',
    referenceTool: 'Reactome Analysis Service-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'DEMO Reactome-like result',
    topN: 3,
    bionexus: {
      pathways: [
        { stId: 'R-HSA-DEMO-001', name: 'DNA repair demo pathway', geneRatio: 0.42, entitiesFDR: 0.0008 },
        { stId: 'R-HSA-DEMO-002', name: 'Cell-cycle demo pathway', geneRatio: 0.35, entitiesFDR: 0.0021 },
        { stId: 'R-HSA-DEMO-003', name: 'Signal-transduction demo pathway', geneRatio: 0.28, entitiesFDR: 0.0063 },
      ],
    },
    reference: {
      pathways: [
        { stId: 'R-HSA-DEMO-001', name: 'DNA repair demo pathway', geneRatio: 0.41, entitiesFDR: 0.0009 },
        { stId: 'R-HSA-DEMO-002', name: 'Cell-cycle demo pathway', geneRatio: 0.34, entitiesFDR: 0.0024 },
        { stId: 'R-HSA-DEMO-003', name: 'Signal-transduction demo pathway', geneRatio: 0.29, entitiesFDR: 0.0060 },
      ],
    },
  },
  rnaseq: {
    label: 'DESeq2 differential-expression demo',
    description: 'Small deterministic gene-level result set demonstrating log2FC correlation, adjusted-P concordance and significant-gene overlap.',
    referenceTool: 'R/Bioconductor DESeq2-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'Same synthetic count/design fixture',
    bionexus: {
      results: [
        { gene: 'GENE_A', log2FoldChange: 2.15, padj: 0.0004 },
        { gene: 'GENE_B', log2FoldChange: -1.72, padj: 0.003 },
        { gene: 'GENE_C', log2FoldChange: 0.38, padj: 0.41 },
        { gene: 'GENE_D', log2FoldChange: 1.21, padj: 0.018 },
        { gene: 'GENE_E', log2FoldChange: -0.22, padj: 0.73 },
      ],
    },
    reference: {
      results: [
        { gene: 'GENE_A', log2FoldChange: 2.10, padj: 0.0005 },
        { gene: 'GENE_B', log2FoldChange: -1.69, padj: 0.0034 },
        { gene: 'GENE_C', log2FoldChange: 0.35, padj: 0.44 },
        { gene: 'GENE_D', log2FoldChange: 1.18, padj: 0.020 },
        { gene: 'GENE_E', log2FoldChange: -0.19, padj: 0.76 },
      ],
    },
  },
  ngs: {
    label: 'GIAB-style variant benchmark demo',
    description: 'Numeric regression fixture demonstrating TP/FP/FN and derived precision/recall/F1 comparison fields.',
    referenceTool: 'GIAB/hap.py-style demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'Synthetic truth-set regression fixture',
    bionexus: { metrics: { tp: 982, fp: 18, fn: 23, precision: 0.982, recall: 0.9771, f1: 0.9795 } },
    reference: { metrics: { tp: 984, fp: 16, fn: 21, precision: 0.984, recall: 0.9791, f1: 0.9815 } },
  },
  docking: {
    label: 'AutoDock Vina pose-score demo',
    description: 'Pose-level affinity and RMSD-bound fixture for same-input standalone-Vina comparison.',
    referenceTool: 'AutoDock Vina standalone-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'Same receptor/ligand/grid/seed demo',
    bionexus: {
      poses: [
        { affinity: -8.4, rmsd_lb: 0.0, rmsd_ub: 0.0 },
        { affinity: -7.9, rmsd_lb: 1.3, rmsd_ub: 2.1 },
        { affinity: -7.5, rmsd_lb: 1.8, rmsd_ub: 2.8 },
      ],
    },
    reference: {
      poses: [
        { affinity: -8.3, rmsd_lb: 0.0, rmsd_ub: 0.0 },
        { affinity: -7.8, rmsd_lb: 1.2, rmsd_ub: 2.0 },
        { affinity: -7.4, rmsd_lb: 1.9, rmsd_ub: 2.9 },
      ],
    },
  },
  md: {
    label: 'Trajectory-metric demo',
    description: 'Short deterministic trajectory summaries for RMSD, RMSF, radius of gyration, SASA and hydrogen-bond concordance.',
    referenceTool: 'OpenMM/MDAnalysis-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'Same short implicit-solvent trajectory fixture',
    bionexus: {
      rmsd: [0.00, 0.32, 0.48, 0.55, 0.61, 0.64],
      rmsf: [0.42, 0.58, 0.81, 0.63, 0.49, 0.45],
      radius_of_gyration: [14.82, 14.78, 14.75, 14.73, 14.71, 14.70],
      sasa: [6120, 6098, 6085, 6074, 6068, 6063],
      hbonds: [42, 44, 43, 45, 46, 45],
    },
    reference: {
      rmsd: [0.00, 0.31, 0.47, 0.56, 0.60, 0.63],
      rmsf: [0.41, 0.57, 0.79, 0.64, 0.50, 0.46],
      radius_of_gyration: [14.81, 14.79, 14.76, 14.74, 14.72, 14.70],
      sasa: [6118, 6101, 6087, 6076, 6070, 6064],
      hbonds: [42, 43, 44, 45, 45, 46],
    },
  },
  admet: {
    label: 'RDKit descriptor demo',
    description: 'Deterministic descriptor comparison for molecular weight, cLogP, TPSA, H-bond donors/acceptors and rotatable bonds.',
    referenceTool: 'RDKit-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'Same demo molecule',
    bionexus: { descriptors: { molecular_weight: 180.159, clogp: 1.19, tpsa: 63.60, hbd: 1, hba: 4, rotatable_bonds: 2 } },
    reference: { descriptors: { molecular_weight: 180.159, clogp: 1.19, tpsa: 63.60, hbd: 1, hba: 4, rotatable_bonds: 2 } },
  },
  domains: {
    label: 'InterPro domain-overlap demo',
    description: 'Identifier-overlap fixture for two domain annotations.',
    referenceTool: 'InterPro/InterProScan-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'DEMO InterPro-like annotations',
    bionexus: { domains: [{ accession: 'IPR_DEMO_001' }, { accession: 'IPR_DEMO_002' }, { accession: 'IPR_DEMO_003' }] },
    reference: { domains: [{ accession: 'IPR_DEMO_001' }, { accession: 'IPR_DEMO_002' }, { accession: 'IPR_DEMO_004' }] },
  },
  motif: {
    label: 'PROSITE motif-overlap demo',
    description: 'Identifier-overlap fixture for motif calls.',
    referenceTool: 'PROSITE-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'DEMO motif annotations',
    bionexus: { motifs: [{ id: 'PS_DEMO_001' }, { id: 'PS_DEMO_002' }, { id: 'PS_DEMO_003' }] },
    reference: { motifs: [{ id: 'PS_DEMO_001' }, { id: 'PS_DEMO_002' }, { id: 'PS_DEMO_004' }] },
  },
  function: {
    label: 'GO evidence-overlap demo',
    description: 'GO-term set overlap for InterPro2GO/reviewed-annotation style comparison.',
    referenceTool: 'InterPro2GO / UniProtKB-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'DEMO GO evidence',
    bionexus: { go_terms: [{ go_id: 'GO:0003677' }, { go_id: 'GO:0006355' }, { go_id: 'GO:0005634' }] },
    reference: { go_terms: [{ go_id: 'GO:0003677' }, { go_id: 'GO:0006355' }, { go_id: 'GO:0005737' }] },
  },
  interactions: {
    label: 'STRING partner-overlap demo',
    description: 'Top partner overlap and combined-score correlation fixture.',
    referenceTool: 'STRING-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'DEMO same-species interaction set',
    topN: 4,
    bionexus: {
      interactions: [
        { partner_gene: 'PARTNER_A', combined_score: 0.94 },
        { partner_gene: 'PARTNER_B', combined_score: 0.88 },
        { partner_gene: 'PARTNER_C', combined_score: 0.81 },
        { partner_gene: 'PARTNER_D', combined_score: 0.73 },
      ],
    },
    reference: {
      interactions: [
        { partner_gene: 'PARTNER_A', combined_score: 0.93 },
        { partner_gene: 'PARTNER_B', combined_score: 0.89 },
        { partner_gene: 'PARTNER_C', combined_score: 0.80 },
        { partner_gene: 'PARTNER_E', combined_score: 0.71 },
      ],
    },
  },
  structure: {
    label: 'Structure-metric demo',
    description: 'Numeric structural-quality fixture for same-structure reference analysis.',
    referenceTool: 'RCSB/reference structural-analysis demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'Same structure demo',
    bionexus: { metrics: { residue_count: 141, ramachandran_favored_pct: 97.2, clashscore: 3.8, mean_bfactor: 21.4 } },
    reference: { metrics: { residue_count: 141, ramachandran_favored_pct: 97.0, clashscore: 4.0, mean_bfactor: 21.3 } },
  },
  castp: {
    label: 'Pocket-metric demo',
    description: 'Numeric pocket geometry fixture for volume, area and residue count.',
    referenceTool: 'CASTp-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'Same structure/pocket demo',
    bionexus: { metrics: { pocket_volume: 612.4, pocket_area: 438.2, residue_count: 22 } },
    reference: { metrics: { pocket_volume: 609.8, pocket_area: 440.1, residue_count: 22 } },
  },
  uniprot: {
    label: 'UniProt annotation-overlap demo',
    description: 'GO/feature identifier overlap for a same-accession reference record.',
    referenceTool: 'UniProtKB-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'DEMO reviewed record',
    bionexus: { features: [{ id: 'ACT_SITE_1' }, { id: 'BINDING_2' }, { id: 'DOMAIN_3' }] },
    reference: { features: [{ id: 'ACT_SITE_1' }, { id: 'BINDING_2' }, { id: 'DOMAIN_3' }] },
  },
  pairwise: {
    label: 'EMBOSS pairwise-alignment demo',
    description: 'Numeric pairwise-alignment metrics for score, identity, aligned length and gap count.',
    referenceTool: 'EMBOSS Needle/Water-compatible demo fixture',
    referenceVersion: 'fixture-v1',
    referenceDatabase: 'Same two sequences and scoring settings',
    bionexus: { metrics: { alignment_score: 81.5, identity_pct: 92.1, alignment_length: 76, gap_count: 2 } },
    reference: { metrics: { alignment_score: 81.0, identity_pct: 92.1, alignment_length: 76, gap_count: 2 } },
  },
};

export function getScientificComparisonSample(analysisType: string): ScientificComparisonSample | null {
  return SCIENTIFIC_COMPARISON_SAMPLES[analysisType] ?? null;
}
