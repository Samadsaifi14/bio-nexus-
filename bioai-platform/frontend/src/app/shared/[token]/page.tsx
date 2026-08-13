'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Dna, CircleNotch as LoaderCircle } from '@phosphor-icons/react';
import type { JobStatus } from '@/types/pipeline';
import { getSharedResult } from '@/lib/api';
import { AIInterpretation } from '@/components/results/AIInterpretation';
import { BlastPanel } from '@/components/results/BlastPanel';
import { ScoreBars } from '@/components/results/ScoreBars';
import { UniprotPanel } from '@/components/results/UniprotPanel';
import { AlphaFoldViewer } from '@/components/AlphaFoldViewer';
import { PathwayEnrichment } from '@/components/results/PathwayEnrichment';
import PhyloTreeViewer from "@/components/phylo/PhyloTreeViewer";
import { AlignmentStatsBar } from "@/components/alignment/AlignmentStatsBar";
import { AlignmentBlock } from "@/components/alignment/AlignmentBlock";
import { computeAlignmentStats, parseAlignedFasta } from "@/lib/alignment-stats";
import { motion } from 'framer-motion';
import { fadeUp, stagger } from '@/lib/animations';

export default function SharedResultPage() {
  const params = useParams();
  const token = params.token as string;
  const [job, setJob] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSharedResult(token)
      .then(setJob)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-void">
        <LoaderCircle className="w-8 h-8 text-accent-cyan animate-spin" />
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-void">
        <div className="bg-surface-0 rounded-2xl border border-glass-border p-8 text-center max-w-sm">
          <Dna className="w-12 h-12 text-text-muted mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-text-primary mb-2">Not Found</h2>
          <p className="text-sm text-text-muted">This shared result does not exist or has been removed.</p>
        </div>
      </div>
    );
  }

  const context = job.context_json;

  return (
    <div className="min-h-screen bg-void">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex items-center gap-2 mb-6">
          <Dna className="w-7 h-7 text-accent-cyan" />
          <span className="text-lg font-bold text-text-primary">Synteny — Shared Result</span>
        </div>

        {!context ? (
          <div className="bg-surface-0 rounded-2xl border border-glass-border p-8 text-center">
            <p className="text-sm text-text-muted">This result is from an older version and cannot be displayed in full.</p>
          </div>
        ) : (
          <motion.div variants={stagger} animate="show" className="space-y-6">
            <motion.div variants={fadeUp}>
              <h1 className="text-2xl font-bold text-text-primary mb-1">Analysis Results</h1>
              <p className="text-sm text-text-muted">
                {context.query?.accession
                  ? <>Query: <code className="font-mono text-accent-cyan">{context.query.accession}</code></>
                  : <>Query: {(context.query?.sequence ?? context.sequence ?? 'Unknown sequence').slice(0, 80)}...</>
                } ({context.query?.length ?? context.length ?? '?'} {context.query?.sequence_type === 'dna' ? 'bp' : 'aa'})
              </p>
            </motion.div>

            <motion.div variants={fadeUp}>
              <AIInterpretation context={context} pipelineType={job.pipeline_type} />
            </motion.div>

            <motion.div variants={fadeUp} className="grid lg:grid-cols-2 gap-6">
              {context.blast?.hits && context.blast.hits.length > 0 && (
                <BlastPanel hits={context.blast.hits} count={context.blast.count} source={context.blast.source} querySequence={context.query?.sequence} />
              )}
              {context.uniprot && <UniprotPanel data={context.uniprot} />}
            </motion.div>

            {context.blast?.hits && context.blast.hits.length > 0 && (
              <motion.div variants={fadeUp}>
                <ScoreBars hits={context.blast.hits} />
              </motion.div>
            )}

            {context.msa?.aln_fasta && (
              <motion.div variants={fadeUp} className="bg-surface-0 rounded-2xl border border-glass-border p-5">
                <h3 className="text-sm font-semibold text-text-primary mb-1">Multiple Sequence Alignment</h3>
                <p className="text-xs text-text-muted mb-2">{context.msa.sequence_count ?? 0} sequences aligned via Clustal Omega</p>
                <AlignmentStatsBar
                  stats={computeAlignmentStats(parseAlignedFasta(context.msa.aln_fasta).seqs)}
                  className="mb-2"
                />
                <AlignmentBlock alnFasta={context.msa.aln_fasta} className="max-h-80" />
              </motion.div>
            )}

            {(() => {
              const newick = context.phylo?.phylotree_newick
                || context.phylo_data?.phylotree_newick
                || context.msa?.phylotree;
              return newick ? (
                <motion.div variants={fadeUp} className="bg-surface-0 rounded-2xl border border-glass-border p-5">
                  <h3 className="text-sm font-semibold text-text-primary mb-2">Phylogenetic Tree</h3>
                  <PhyloTreeViewer newick={newick} />
                </motion.div>
              ) : null;
            })()}

            {context.alphafold?.structure_available && (
              <motion.div variants={fadeUp}>
                <AlphaFoldViewer pdbUrl={context.alphafold.pdb_url} uniprotId={context.alphafold.uniprot_accession} />
              </motion.div>
            )}

            {context.pathway_enrichment && (
              <motion.div variants={fadeUp}>
                <PathwayEnrichment data={context.pathway_enrichment} />
              </motion.div>
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
}
