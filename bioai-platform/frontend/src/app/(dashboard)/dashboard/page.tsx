'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import { ArrowRight, ArrowUpRight, CircleNotch, Clock, Flask, MagnifyingGlass, Atom, Dna, CheckCircle } from '@phosphor-icons/react';
import { getJobs, getJobCount } from '@/lib/api';
import { useAuth } from '@/contexts/auth';
import type { JobStatus } from '@/types/pipeline';
import { STEP_LABELS } from '@/types/pipeline';
import { STATUS_TEXT } from '@/lib/status-colors';

const startingPoints = [
  { title: 'Explore sequencing evidence', field: 'Genomics', href: '/analyze/ngs-v2', icon: Dna, description: 'QC, coverage and variant evidence' },
  { title: 'Find sequence similarity', field: 'Sequence biology', href: '/analyze/blast', icon: MagnifyingGlass, description: 'Matches, alignments and reference context' },
  { title: 'Inspect molecular binding', field: 'Structural biology', href: '/analyze/docking', icon: Atom, description: 'Pose and interaction views' },
];

const statusLabel: Record<string, string> = { complete: 'Complete', completed: 'Complete', failed: 'Failed', queued: 'Queued', running: 'Running', submitted_to_ncbi: 'Submitted', polling_ncbi: 'In progress', parsing: 'Parsing', interpreting: 'Interpreting' };

export default function DashboardPage() {
  const { user, isGuest } = useAuth();
  const reduceMotion = useReducedMotion();
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [usage, setUsage] = useState({ count: 0, limit: 10, remaining: 10 });
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getJobs(), getJobCount()])
      .then(([recent, daily]) => { setJobs(recent); setUsage(daily); setFetchError(null); })
      .catch(() => setFetchError('We could not load your recent work. Please try again shortly.'))
      .finally(() => setLoading(false));
  }, []);

  const firstName = (user?.user_metadata?.full_name as string | undefined)?.split(' ')[0];
  const completed = jobs.filter(job => job.status === 'complete').length;
  const failed = jobs.filter(job => job.status === 'failed').length;
  const active = jobs.filter(job => !['complete', 'failed'].includes(job.status)).length;
  const usagePercent = usage.limit > 0 ? Math.min((usage.count / usage.limit) * 100, 100) : 0;
  const enter = reduceMotion ? false : { opacity: 0, y: 16 };

  return <div className="bn-dashboard">
    <motion.section initial={enter} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5 }} className="bn-dashboard-intro">
      <div><p className="bn-kicker">Research desk</p><h1>{isGuest ? 'Welcome to BioNexus.' : `Welcome back${firstName ? `, ${firstName}` : ''}.`}</h1><p>Pick up a result, or start with the question you want to answer.</p></div>
      <Link href="/analyze" className="bn-button bn-button-primary shrink-0">New analysis <ArrowUpRight size={18} aria-hidden="true" /></Link>
    </motion.section>

    {fetchError && <div role="alert" className="bn-dashboard-error">{fetchError}</div>}

    <div className="bn-dashboard-columns">
      <div className="min-w-0">
        <motion.section initial={enter} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5, delay: .08 }} className="bn-dashboard-section">
          <div className="bn-dashboard-section-heading"><div><p className="bn-kicker">Begin here</p><h2>Follow a line of inquiry</h2></div><Link href="/analyze" className="bn-text-link">All methods <ArrowRight size={16} aria-hidden="true" /></Link></div>
          <div className="bn-starting-points">{startingPoints.map((item, index) => { const Icon = item.icon; return <Link href={item.href} key={item.title} className="bn-starting-point group"><span className="bn-start-number">0{index + 1}</span><span className="bn-start-icon"><Icon size={26} aria-hidden="true" /></span><span className="bn-start-body"><small>{item.field}</small><strong>{item.title}</strong><span>{item.description}</span></span><ArrowUpRight className="bn-start-arrow" size={20} aria-hidden="true" /></Link>; })}</div>
          <Link href="/wizard" className="bn-dashboard-guide"><Flask size={21} aria-hidden="true" /><span><strong>Not sure where to begin?</strong><small>Let the guided workflow help you choose a method.</small></span><ArrowRight size={18} aria-hidden="true" /></Link>
        </motion.section>

        <motion.section initial={enter} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5, delay: .14 }} className="bn-dashboard-section">
          <div className="bn-dashboard-section-heading"><div><p className="bn-kicker">Your activity</p><h2>Recent work</h2></div><Link href="/jobs" className="bn-text-link">View jobs <ArrowRight size={16} aria-hidden="true" /></Link></div>
          {loading ? <div role="status" className="bn-dashboard-loading"><CircleNotch size={20} className="animate-spin" aria-hidden="true" /> Loading recent work</div> : jobs.length ? <div className="bn-job-list">{jobs.slice(0, 5).map(job => {
            const label = job.current_step_label || STEP_LABELS[job.status as keyof typeof STEP_LABELS] || job.status;
            return <Link key={job.id} href={`/jobs/${job.id}`} className="bn-job-row group"><span className={`bn-job-status ${STATUS_TEXT[job.status] || 'text-text-muted'}`}><span className="bn-status-dot" />{statusLabel[job.status] || job.status}</span><span className="bn-job-title">{label}</span><span className="bn-job-date">{job.created_at ? new Date(job.created_at).toLocaleDateString() : 'Date unavailable'}</span><ArrowUpRight size={17} className="bn-job-arrow" aria-hidden="true" /></Link>;
          })}</div> : <div className="bn-dashboard-empty"><Clock size={25} aria-hidden="true" /><h3>Your work will appear here.</h3><p>Start a method, then return to review its status and results.</p><Link href="/analyze">Explore methods <ArrowRight size={16} aria-hidden="true" /></Link></div>}
        </motion.section>
      </div>

      <motion.aside initial={enter} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5, delay: .2 }} className="bn-dashboard-aside" aria-label="Workspace overview">
        <p className="bn-kicker">At a glance</p><h2>Workspace pulse</h2>
        {loading ? <div role="status" className="bn-dashboard-loading"><CircleNotch size={18} className="animate-spin" aria-hidden="true" /> Loading overview</div> : <>
          <dl className="bn-pulse-grid"><div><dt>Total runs</dt><dd>{jobs.length}</dd></div><div><dt>In progress</dt><dd>{active}</dd></div><div><dt>Completed</dt><dd>{completed}</dd></div><div><dt>Need review</dt><dd>{failed}</dd></div></dl>
          <div className="bn-usage"><div className="flex items-center justify-between gap-4"><h3>Today&apos;s usage</h3><span>{usage.count} / {usage.limit}</span></div><div className="bn-usage-track" role="progressbar" aria-label="Daily analysis usage" aria-valuenow={usage.count} aria-valuemin={0} aria-valuemax={usage.limit || 1}><motion.span initial={reduceMotion ? false : { width: 0 }} animate={{ width: `${usagePercent}%` }} transition={{ duration: .8, ease: 'easeOut' }} /></div><p>{usage.remaining} {usage.remaining === 1 ? 'analysis' : 'analyses'} remaining today</p></div>
        </>}
        <div className="bn-aside-note"><CheckCircle size={20} aria-hidden="true" /><p>Read results alongside their method, status and quality checks. A missing value does not mean a negative finding.</p></div>
        {isGuest && <Link href="/auth" className="bn-aside-signin">Sign in to keep your history <ArrowUpRight size={16} aria-hidden="true" /></Link>}
      </motion.aside>
    </div>
  </div>;
}
