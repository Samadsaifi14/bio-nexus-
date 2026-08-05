'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getJobs } from '@/lib/api';
import type { JobStatus } from '@/types/pipeline';
import { motion } from 'framer-motion';
import { fadeUp, stagger } from '@/lib/animations';
import { CircleNotch as LoaderCircle, FileText, Dna } from '@phosphor-icons/react';
import { PageHeader } from '@/components/ui';
import { STATUS_BADGE } from '@/lib/status-colors';

export default function HistoryPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getJobs()
      .then(setJobs)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <LoaderCircle className="w-8 h-8 text-accent-cyan animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card p-6 text-center">
        <p className="text-sm text-error">Failed to load history: {error}</p>
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="glass-card p-16 text-center">
        <FileText className="w-16 h-16 text-text-muted mx-auto mb-6" />
        <h3 className="text-xl font-semibold text-text-primary mb-2">No history yet</h3>
        <p className="text-sm text-text-secondary mb-6">Run your first analysis to see results here.</p>
        <a href="/analyze" className="btn-critical text-sm inline-flex items-center gap-2">
          <Dna className="w-4 h-4" />
          Run your first sequence
        </a>
      </div>
    );
  }

  return (
    <div className="max-w-4xl">
      <PageHeader title="Analysis history" />
      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-glass-border bg-surface-1">
              <th className="px-4 py-3 text-left font-medium text-text-muted w-28">Job ID</th>
              <th className="px-4 py-3 text-left font-medium text-text-muted">Pipeline</th>
              <th className="px-4 py-3 text-left font-medium text-text-muted w-28">Status</th>
              <th className="px-4 py-3 text-left font-medium text-text-muted hidden sm:table-cell">Created</th>
            </tr>
          </thead>
          <motion.tbody variants={stagger} animate="show">
            {jobs.map((job) => (
              <motion.tr
                key={job.id}
                variants={fadeUp}
                onClick={() => router.push(`/results/${job.id}`)}
                className="border-b border-glass-border hover:bg-surface-1 cursor-pointer transition-colors last:border-0"
              >
                <td className="px-4 py-3 font-mono text-xs text-text-muted">
                  {job.id.slice(0, 8)}...
                </td>
                <td className="px-4 py-3 text-text-secondary capitalize">
                  {(job.pipeline_type ?? 'protein_analysis').replace(/_/g, ' ')}
                </td>
                <td className="px-4 py-3">
                  <span className={STATUS_BADGE[job.status] ?? 'badge bg-surface-2 text-text-muted text-[10px]'}>
                    {job.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-text-muted text-xs hidden sm:table-cell">
                  {new Date(job.created_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                </td>
              </motion.tr>
            ))}
          </motion.tbody>
        </table>
      </motion.div>
    </div>
  );
}
