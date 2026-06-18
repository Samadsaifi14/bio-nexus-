'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { fadeUp, stagger, cardHover } from '@/lib/animations';
import { LoaderCircle, Dna, FileText, Clock, CheckCircle, XCircle, Plus } from 'lucide-react';
import { getJobs } from '@/lib/api';
import type { JobStatus } from '@/types/pipeline';
import { STEP_LABELS } from '@/types/pipeline';

const STATUS_ICONS: Record<string, typeof Clock> = {
  queued: Clock,
  submitted_to_ncbi: Clock,
  polling_ncbi: Clock,
  parsing: Clock,
  interpreting: Clock,
  complete: CheckCircle,
  failed: XCircle,
};

const STATUS_COLORS: Record<string, string> = {
  queued: 'text-text-muted',
  submitted_to_ncbi: 'text-accent-cyan',
  polling_ncbi: 'text-accent-cyan',
  parsing: 'text-accent-cyan',
  interpreting: 'text-accent-cyan',
  complete: 'text-accent-cyan',
  failed: 'text-error',
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getJobs()
      .then(setJobs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <LoaderCircle className="w-8 h-8 text-accent-cyan animate-spin" />
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="glass-card p-16 text-center">
        <FileText className="w-16 h-16 text-text-muted mx-auto mb-6" />
        <h3 className="text-xl font-semibold text-text-primary mb-2">No jobs yet</h3>
        <p className="text-sm text-text-secondary mb-6">Run your first analysis to see results here.</p>
        <Link
          href="/analyze"
          className="inline-flex items-center gap-2 px-6 py-3 btn-primary text-sm"
        >
          <Dna className="w-4 h-4" />
          Start Analysis
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <motion.h1 variants={fadeUp} className="text-2xl font-bold text-text-primary">Your Jobs</motion.h1>
        <Link
          href="/analyze"
          className="btn-primary px-4 py-2 text-sm flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          New Analysis
        </Link>
      </div>

      <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-3">
      {jobs.map((job) => {
        const Icon = STATUS_ICONS[job.status] || Clock;
        const color = STATUS_COLORS[job.status] || 'text-text-muted';
        const label = job.current_step_label || STEP_LABELS[job.status as keyof typeof STEP_LABELS] || job.status;
        const isComplete = job.status === 'complete';

        return (
          <motion.div key={job.id} variants={fadeUp} whileHover={cardHover}>
          <Link
            href={`/jobs/${job.id}`}
            className="block glass-card p-5 hover:bg-surface-2 transition"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Icon className={`w-4 h-4 ${color}`} />
                  <span className={`text-sm font-medium ${isComplete ? 'text-text-primary' : 'text-accent-cyan'}`}>
                    {label}
                  </span>
                  {isComplete && (
                    <span className="badge bg-accent-cyan/10 text-accent-cyan text-[10px]">Complete</span>
                  )}
                  {job.status === 'failed' && (
                    <span className="badge bg-error/10 text-error text-[10px]">Failed</span>
                  )}
                </div>
                {job.context_json?.query?.sequence && (
                  <p className="text-sm text-text-muted truncate mt-1">
                    {job.context_json.query.sequence.slice(0, 100)}...
                  </p>
                )}
              </div>
              <div className="text-xs text-text-muted shrink-0 ml-4">
                {new Date(job.created_at || Date.now()).toLocaleDateString()}
              </div>
            </div>
          </Link>
          </motion.div>
        );
      })}
      </motion.div>
    </div>
  );
}
