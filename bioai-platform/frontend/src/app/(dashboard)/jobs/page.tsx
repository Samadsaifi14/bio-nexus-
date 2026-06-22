'use client';

import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { fadeUp, stagger, cardHover } from '@/lib/animations';
import {
  LoaderCircle, Dna, FileText, Clock, CheckCircle, XCircle, Plus, ChevronRight,
} from 'lucide-react';
import { getJobs } from '@/lib/api';
import type { JobStatus } from '@/types/pipeline';
import { STEP_LABELS } from '@/types/pipeline';

const STATUS_ICONS: Record<string, typeof Clock> = {
  queued: Clock, submitted_to_ncbi: Clock, polling_ncbi: Clock,
  parsing: Clock, interpreting: Clock, complete: CheckCircle, failed: XCircle,
};
const STATUS_COLORS: Record<string, string> = {
  queued: 'text-text-muted', submitted_to_ncbi: 'text-accent-cyan',
  polling_ncbi: 'text-accent-cyan', parsing: 'text-accent-cyan',
  interpreting: 'text-accent-cyan', complete: 'text-accent-cyan', failed: 'text-error',
};

const ACTIVE_STATUSES = ['queued', 'submitted_to_ncbi', 'polling_ncbi', 'parsing', 'interpreting'];

type FilterTab = 'all' | 'active' | 'complete' | 'failed';

function timeAgo(iso: string | undefined): string {
  if (!iso) return '';
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60)   return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400)return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function JobsPage() {
  const [jobs, setJobs]     = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter]   = useState<FilterTab>('all');

  useEffect(() => {
    getJobs().then(setJobs).catch(console.error).finally(() => setLoading(false));
  }, []);

  const counts = useMemo(() => ({
    all:      jobs.length,
    active:   jobs.filter(j => ACTIVE_STATUSES.includes(j.status)).length,
    complete: jobs.filter(j => j.status === 'complete').length,
    failed:   jobs.filter(j => j.status === 'failed').length,
  }), [jobs]);

  const filtered = useMemo(() => {
    if (filter === 'all')      return jobs;
    if (filter === 'active')   return jobs.filter(j => ACTIVE_STATUSES.includes(j.status));
    return jobs.filter(j => j.status === filter);
  }, [jobs, filter]);

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <LoaderCircle className="w-8 h-8 text-accent-cyan animate-spin" />
    </div>
  );

  if (jobs.length === 0) return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text-primary">Jobs</h1>
        <Link href="/analyze" className="btn-primary px-4 py-2 text-sm flex items-center gap-2">
          <Plus className="w-4 h-4" /> New Analysis
        </Link>
      </div>
      <div className="glass-card p-16 text-center">
        <FileText className="w-16 h-16 text-text-muted mx-auto mb-6" />
        <h3 className="text-xl font-semibold text-text-primary mb-2">No jobs yet</h3>
        <p className="text-sm text-text-secondary mb-6">Run your first analysis to see results here.</p>
        <Link href="/analyze" className="inline-flex items-center gap-2 px-6 py-3 btn-primary text-sm">
          <Dna className="w-4 h-4" /> Start Analysis
        </Link>
      </div>
    </div>
  );

  const TABS: { key: FilterTab; label: string }[] = [
    { key: 'all',      label: 'All'      },
    { key: 'active',   label: 'Active'   },
    { key: 'complete', label: 'Complete' },
    { key: 'failed',   label: 'Failed'   },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <motion.h1 variants={fadeUp} className="text-2xl font-bold text-text-primary">Jobs</motion.h1>
          <p className="text-sm text-text-muted mt-0.5">
            {jobs.length} total · {counts.complete} complete · {counts.active} active
          </p>
        </div>
        <Link href="/analyze" className="btn-primary px-4 py-2 text-sm flex items-center gap-2 shrink-0">
          <Plus className="w-4 h-4" /> New Analysis
        </Link>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-1 p-1 glass-card w-fit rounded-xl">
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition flex items-center gap-2 ${
              filter === tab.key
                ? 'bg-accent-cyan/15 text-accent-cyan'
                : 'text-text-muted hover:text-text-primary'
            }`}
          >
            {tab.label}
            {counts[tab.key] > 0 && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                filter === tab.key ? 'bg-accent-cyan/20 text-accent-cyan' : 'bg-surface-1 text-text-muted'
              }`}>
                {counts[tab.key]}
              </span>
            )}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="glass-card p-10 text-center">
          <p className="text-sm text-text-muted">No {filter} jobs.</p>
        </div>
      ) : (
        <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-2">
          {filtered.map(job => {
            const Icon       = STATUS_ICONS[job.status] || Clock;
            const color      = STATUS_COLORS[job.status] || 'text-text-muted';
            const label      = job.current_step_label || STEP_LABELS[job.status as keyof typeof STEP_LABELS] || job.status;
            const isComplete = job.status === 'complete';
            const isFailed   = job.status === 'failed';
            const isActive   = ACTIVE_STATUSES.includes(job.status);

            return (
              <motion.div key={job.id} variants={fadeUp} whileHover={cardHover}>
                <Link href={`/jobs/${job.id}`} className="flex items-center gap-4 glass-card p-4 hover:bg-surface-2 transition group">
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                    isComplete ? 'bg-accent-cyan/10' : isFailed ? 'bg-error/10' : 'bg-surface-1'
                  }`}>
                    <Icon className={`w-4 h-4 ${color} ${isActive ? 'animate-pulse' : ''}`} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium truncate group-hover:text-accent-cyan transition ${
                      isActive ? 'text-accent-cyan' : 'text-text-primary'
                    }`}>
                      {label}
                    </p>
                    {job.context_json?.query?.sequence && (
                      <p className="text-[11px] text-text-muted font-mono truncate mt-0.5">
                        {job.context_json.query.sequence.slice(0, 90)}…
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    {isComplete && <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-cyan/10 text-accent-cyan font-medium">Done</span>}
                    {isFailed   && <span className="text-[10px] px-2 py-0.5 rounded-full bg-error/10 text-error font-medium">Failed</span>}
                    {isActive   && <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-purple/10 text-accent-purple font-medium">Running</span>}
                    <div className="text-right hidden sm:block">
                      <p className="text-xs text-text-muted">{new Date(job.created_at || Date.now()).toLocaleDateString()}</p>
                      <p className="text-[10px] text-text-muted/50">{timeAgo(job.created_at)}</p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-text-muted group-hover:text-accent-cyan transition" />
                  </div>
                </Link>
              </motion.div>
            );
          })}
        </motion.div>
      )}
    </div>
  );
}