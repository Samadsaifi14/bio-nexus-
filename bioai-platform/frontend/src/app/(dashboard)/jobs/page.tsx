'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { fadeUp, stagger, cardHover } from '@/lib/animations';
import { Loader2, Dna, FileText, AlertCircle, Clock, CheckCircle, XCircle } from 'lucide-react';
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
  queued: 'text-gray-400',
  submitted_to_ncbi: 'text-teal-500',
  polling_ncbi: 'text-teal-500',
  parsing: 'text-teal-500',
  interpreting: 'text-teal-500',
  complete: 'text-teal-600',
  failed: 'text-red-500',
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
        <Loader2 className="w-8 h-8 text-teal-500 animate-spin" />
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-16 text-center">
        <FileText className="w-16 h-16 text-gray-200 mx-auto mb-6" />
        <h3 className="text-xl font-semibold text-gray-900 mb-2">No jobs yet</h3>
        <p className="text-sm text-gray-500 mb-6">Run your first analysis to see results here.</p>
        <Link
          href="/analyze"
          className="inline-flex items-center gap-2 px-6 py-3 bg-teal-600 text-white text-sm font-medium rounded-xl hover:bg-teal-700 transition"
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
        <motion.h1 variants={fadeUp} className="text-2xl font-bold text-gray-900">Your Jobs</motion.h1>
        <Link
          href="/analyze"
          className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition"
        >
          New Analysis
        </Link>
      </div>

      <motion.div variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, margin: '-40px' }}>
      {jobs.map((job) => {
        const Icon = STATUS_ICONS[job.status] || Clock;
        const color = STATUS_COLORS[job.status] || 'text-gray-400';
        const label = job.current_step_label || STEP_LABELS[job.status as keyof typeof STEP_LABELS] || job.status;
        const isComplete = job.status === 'complete';

        return (
          <motion.div key={job.id} variants={fadeUp} whileHover={cardHover}>
          <Link
            href={`/jobs/${job.id}`}
            className="block bg-white rounded-2xl border border-gray-200 p-5 hover:border-teal-300 hover:shadow-sm transition"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Icon className={`w-4 h-4 ${color}`} />
                  <span className={`text-sm font-medium ${isComplete ? 'text-gray-900' : 'text-teal-700'}`}>
                    {label}
                  </span>
                  {isComplete && (
                    <span className="text-xs bg-teal-50 text-teal-700 px-2 py-0.5 rounded-full">Complete</span>
                  )}
                  {job.status === 'failed' && (
                    <span className="text-xs bg-red-50 text-red-600 px-2 py-0.5 rounded-full">Failed</span>
                  )}
                </div>
                {job.context_json?.query?.sequence && (
                  <p className="text-sm text-gray-500 truncate mt-1">
                    {job.context_json.query.sequence.slice(0, 100)}...
                  </p>
                )}
              </div>
              <div className="text-xs text-gray-400 shrink-0 ml-4">
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
