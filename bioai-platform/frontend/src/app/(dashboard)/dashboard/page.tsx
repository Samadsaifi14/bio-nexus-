'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { fadeUp, stagger, cardHover } from '@/lib/animations';
import {
  LoaderCircle, Dna, Play, Clock, CheckCircle, XCircle,
  TrendingUp, BarChart3, GitBranch, AlignLeft, FlaskConical,
  Network, Search, ChevronRight, Activity, Calendar,
} from 'lucide-react';
import { getJobs, getJobCount } from '@/lib/api';
import { useAuth } from '@/contexts/auth';
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

const QUICK_TOOLS = [
  { icon: Dna,         label: 'BLAST',        desc: 'Sequence similarity',  href: '/analyze',              color: 'text-accent-cyan',   bg: 'bg-accent-cyan/10'   },
  { icon: GitBranch,   label: 'Phylogeny',    desc: 'NJ / UPGMA / ML',      href: '/analyze/phylo',        color: 'text-accent-purple', bg: 'bg-accent-purple/10' },
  { icon: AlignLeft,   label: 'Alignment',    desc: 'MSA via Clustal',      href: '/analyze/alignment',    color: 'text-accent-amber',  bg: 'bg-accent-amber/10'  },
  { icon: FlaskConical,label: 'Structure',    desc: 'AlphaFold 3D viewer',  href: '/analyze/structure',    color: 'text-accent-cyan',   bg: 'bg-accent-cyan/10'   },
  { icon: Network,     label: 'Interactions', desc: 'PPI via STRING',       href: '/analyze/interactions', color: 'text-accent-purple', bg: 'bg-accent-purple/10' },
  { icon: Search,      label: 'Primers',      desc: 'PCR primer design',    href: '/analyze/primers',      color: 'text-accent-amber',  bg: 'bg-accent-amber/10'  },
];

function getInitials(name?: string, email?: string): string {
  if (name) return name.split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase();
  if (email) return email[0].toUpperCase();
  return 'G';
}

export default function DashboardPage() {
  const { user, isGuest } = useAuth();
  const [jobs, setJobs]   = useState<JobStatus[]>([]);
  const [usage, setUsage] = useState({ count: 0, limit: 10, remaining: 10 });
  const [loading, setLoading]     = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getJobs(), getJobCount()])
      .then(([j, u]) => { setJobs(j); setUsage(u); setFetchError(null); })
      .catch(err  => { setFetchError('Failed to load data — check your connection'); console.error(err); })
      .finally(() => setLoading(false));
  }, []);

  const recentJobs      = jobs.slice(0, 5);
  const completedCount  = jobs.filter(j => j.status === 'complete').length;
  const failedCount     = jobs.filter(j => j.status === 'failed').length;
  const activeCount     = jobs.filter(j => !['complete', 'failed'].includes(j.status)).length;
  const usagePercent    = Math.min(Math.round((usage.count / usage.limit) * 100), 100);

  const fullName  = user?.user_metadata?.full_name as string | undefined;
  const firstName = fullName?.split(' ')[0];
  const initials  = getInitials(fullName, user?.email);
  const today     = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <LoaderCircle className="w-8 h-8 text-accent-cyan animate-spin" />
    </div>
  );

  return (
    <div className="space-y-8">
      {fetchError && (
        <div className="glass-card p-4 border border-accent-amber/20 bg-accent-amber/5">
          <p className="text-sm text-accent-amber">{fetchError}</p>
        </div>
      )}

      {/* ── Header ── */}
      <motion.div variants={fadeUp} className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-accent-cyan/15 border border-accent-cyan/25 flex items-center justify-center shrink-0">
            <span className="text-accent-cyan font-bold text-lg tracking-tight">{initials}</span>
          </div>
          <div>
            <h1 className="text-2xl font-bold text-text-primary">
              {isGuest ? 'Welcome to Bio Nexus' : `Hey, ${firstName ?? 'Researcher'}`}
            </h1>
            <div className="flex items-center gap-1.5 mt-0.5">
              <Calendar className="w-3.5 h-3.5 text-text-muted" />
              <p className="text-sm text-text-muted">{today}</p>
            </div>
          </div>
        </div>
        <Link href="/analyze" className="btn-primary px-5 py-2.5 text-sm flex items-center gap-2 shrink-0">
          <Play className="w-4 h-4" />
          New Analysis
        </Link>
      </motion.div>

      {/* ── Daily usage bar ── */}
      <motion.div variants={fadeUp} className="glass-card p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-accent-cyan" />
            <span className="text-sm font-medium text-text-primary">Daily Usage</span>
          </div>
          <span className="text-sm text-text-muted">{usage.count} / {usage.limit} analyses</span>
        </div>
        <div className="h-1.5 bg-surface-0 rounded-full overflow-hidden border border-glass-border">
          <motion.div
            className={`h-full rounded-full ${usagePercent >= 80 ? 'bg-accent-amber' : 'bg-accent-cyan'}`}
            initial={{ width: 0 }}
            animate={{ width: `${usagePercent}%` }}
            transition={{ duration: 0.9, ease: 'easeOut' }}
          />
        </div>
        <p className="text-xs text-text-muted mt-2">
          {usage.remaining} {usage.remaining === 1 ? 'analysis' : 'analyses'} remaining today
          {isGuest && (
            <span className="ml-2 text-accent-cyan">
              · <Link href="/auth" className="underline underline-offset-2 hover:text-accent-cyan/80 transition">Sign in to keep history</Link>
            </span>
          )}
        </p>
      </motion.div>

      {/* ── Stats ── */}
      <motion.div variants={stagger} initial="hidden" animate="show" className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { icon: BarChart3,   label: 'Total Jobs', value: jobs.length,     color: 'text-accent-cyan',   bg: 'bg-accent-cyan/10',   sub: 'all time' },
          { icon: CheckCircle, label: 'Completed',  value: completedCount,  color: 'text-accent-cyan',   bg: 'bg-accent-cyan/10',   sub: jobs.length ? `${Math.round((completedCount / jobs.length) * 100)}% rate` : '—' },
          { icon: TrendingUp,  label: 'Active',     value: activeCount,     color: 'text-accent-purple', bg: 'bg-accent-purple/10', sub: 'in progress' },
          { icon: XCircle,     label: 'Failed',     value: failedCount,     color: 'text-error',         bg: 'bg-error/10',         sub: 'need review' },
        ].map(s => (
          <motion.div key={s.label} variants={fadeUp} whileHover={cardHover} className="glass-card p-4">
            <div className={`w-8 h-8 ${s.bg} rounded-lg flex items-center justify-center mb-3`}>
              <s.icon className={`w-4 h-4 ${s.color}`} />
            </div>
            <div className="text-2xl font-bold text-text-primary">{s.value}</div>
            <div className="text-xs font-medium text-text-muted mt-0.5">{s.label}</div>
            <div className="text-[11px] text-text-muted/50 mt-0.5">{s.sub}</div>
          </motion.div>
        ))}
      </motion.div>

      {/* ── Quick tools ── */}
      <div>
        <motion.div variants={fadeUp} className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-text-primary">Quick Tools</h2>
          <Link href="/analyze" className="text-sm text-accent-cyan hover:text-accent-cyan/80 font-medium transition flex items-center gap-1">
            All tools <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </motion.div>
        <motion.div variants={stagger} initial="hidden" animate="show" className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {QUICK_TOOLS.map(t => (
            <motion.div key={t.label} variants={fadeUp} whileHover={cardHover}>
              <Link href={t.href} className="glass-card p-4 flex items-center gap-3 hover:bg-surface-2 transition group">
                <div className={`w-9 h-9 ${t.bg} rounded-xl flex items-center justify-center shrink-0`}>
                  <t.icon className={`w-4 h-4 ${t.color}`} />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-text-primary group-hover:text-accent-cyan transition truncate">{t.label}</p>
                  <p className="text-[11px] text-text-muted truncate">{t.desc}</p>
                </div>
              </Link>
            </motion.div>
          ))}
        </motion.div>
      </div>

      {/* ── Recent activity ── */}
      <div>
        <motion.div variants={fadeUp} className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-text-primary">Recent Activity</h2>
          {jobs.length > 5 && (
            <Link href="/jobs" className="text-sm text-accent-cyan hover:text-accent-cyan/80 font-medium transition flex items-center gap-1">
              View all <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          )}
        </motion.div>

        {recentJobs.length > 0 ? (
          <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-2">
            {recentJobs.map(job => {
              const Icon     = STATUS_ICONS[job.status] || Clock;
              const color    = STATUS_COLORS[job.status] || 'text-text-muted';
              const label    = job.current_step_label || STEP_LABELS[job.status as keyof typeof STEP_LABELS] || job.status;
              const isComplete = job.status === 'complete';
              const isFailed   = job.status === 'failed';
              return (
                <motion.div key={job.id} variants={fadeUp}>
                  <Link href={`/jobs/${job.id}`} className="flex items-center gap-3 glass-card p-4 hover:bg-surface-2 transition group">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${isComplete ? 'bg-accent-cyan/10' : isFailed ? 'bg-error/10' : 'bg-surface-1'}`}>
                      <Icon className={`w-4 h-4 ${color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-text-primary group-hover:text-accent-cyan transition truncate">{label}</p>
                      {job.context_json?.query?.sequence && (
                        <p className="text-[11px] text-text-muted font-mono truncate mt-0.5">
                          {job.context_json.query.sequence.slice(0, 72)}…
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      {isComplete && <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-cyan/10 text-accent-cyan font-medium">Done</span>}
                      {isFailed   && <span className="text-[10px] px-2 py-0.5 rounded-full bg-error/10 text-error font-medium">Failed</span>}
                      <span className="text-xs text-text-muted">{new Date(job.created_at || Date.now()).toLocaleDateString()}</span>
                      <ChevronRight className="w-3.5 h-3.5 text-text-muted group-hover:text-accent-cyan transition" />
                    </div>
                  </Link>
                </motion.div>
              );
            })}
          </motion.div>
        ) : (
          <motion.div variants={fadeUp} whileHover={cardHover} className="glass-card p-12 text-center">
            <Dna className="w-12 h-12 text-text-muted mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-text-primary mb-2">Run your first analysis</h3>
            <p className="text-sm text-text-secondary mb-6 max-w-sm mx-auto">
              Submit a protein or nucleotide sequence — BLAST, annotate, visualize structure, and get AI interpretation.
            </p>
            <Link href="/analyze" className="inline-flex items-center gap-2 px-6 py-3 btn-primary text-sm">
              <Play className="w-4 h-4" />
              Start Analysis
            </Link>
          </motion.div>
        )}
      </div>
    </div>
  );
}