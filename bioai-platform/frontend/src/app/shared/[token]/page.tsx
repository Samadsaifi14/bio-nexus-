'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Dna, LoaderCircle } from 'lucide-react';
import type { JobStatus } from '@/types/pipeline';
import { ThemeToggle } from '@/components/ThemeToggle';
import { getSharedResult } from '@/lib/api';
import { AIInterpretation } from '@/components/results/AIInterpretation';
import { BlastPanel } from '@/components/results/BlastPanel';
import { ScoreBars } from '@/components/results/ScoreBars';
import { UniprotPanel } from '@/components/results/UniprotPanel';
import { AlphaFoldViewer } from '@/components/AlphaFoldViewer';
import { PathwayEnrichment } from '@/components/results/PathwayEnrichment';
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
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-teal-50 to-white">
        <div className="absolute top-4 right-4">
          <ThemeToggle compact />
        </div>
        <LoaderCircle className="w-8 h-8 text-teal-600 animate-spin" />
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-teal-50 to-white">
        <div className="absolute top-4 right-4">
          <ThemeToggle compact />
        </div>
        <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center max-w-sm">
          <Dna className="w-12 h-12 text-gray-200 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Not Found</h2>
          <p className="text-sm text-gray-500">This shared result does not exist or has been removed.</p>
        </div>
      </div>
    );
  }

  const context = job.context_json;

  return (
    <div className="min-h-screen bg-gradient-to-b from-teal-50 to-white">
      <div className="absolute top-4 right-4 z-10">
        <ThemeToggle compact />
      </div>
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex items-center gap-2 mb-6">
          <Dna className="w-7 h-7 text-teal-600" />
          <span className="text-lg font-bold text-gray-900">Bio Nexus — Shared Result</span>
        </div>

        {!context ? (
          <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center">
            <p className="text-sm text-gray-500">This result is from an older version and cannot be displayed in full.</p>
          </div>
        ) : (
          <motion.div variants={stagger} animate="show" className="space-y-6">
            <motion.div variants={fadeUp}>
              <h1 className="text-2xl font-bold text-gray-900 mb-1">Analysis Results</h1>
              <p className="text-sm text-gray-500">
                {context.query.accession
                  ? <>Query: <code className="font-mono text-cyan-600">{context.query.accession}</code></>
                  : <>Query: {context.query.sequence.slice(0, 80)}...</>
                } ({context.query.length} {context.query.sequence_type === 'dna' ? 'bp' : 'aa'})
              </p>
            </motion.div>

            <motion.div variants={fadeUp}>
              <AIInterpretation context={context} pipelineType={job.pipeline_type} />
            </motion.div>

            <motion.div variants={fadeUp} className="grid lg:grid-cols-2 gap-6">
              {context.blast?.hits && context.blast.hits.length > 0 && (
                <BlastPanel hits={context.blast.hits} count={context.blast.count} source={context.blast.source} />
              )}
              {context.uniprot && <UniprotPanel data={context.uniprot} />}
            </motion.div>

            {context.blast?.hits && context.blast.hits.length > 0 && (
              <motion.div variants={fadeUp}>
                <ScoreBars hits={context.blast.hits} />
              </motion.div>
            )}

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
