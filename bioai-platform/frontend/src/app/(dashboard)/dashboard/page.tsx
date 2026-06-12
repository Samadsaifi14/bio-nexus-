'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Loader2, Dna, Play, Clock, CheckCircle, XCircle, FileText, TrendingUp, BarChart3 } from 'lucide-react';
import { getJobs, getJobCount } from '@/lib/api';
import { useAuth } from '@/contexts/auth';
import type { JobStatus } from '@/types/pipeline';
import { STEP_LABELS } from '@/types/pipeline';

const STATUS_ICONS: Record<string, typeof Clock> = {
  queued: Clock, submitted_to_ncbi: Clock, polling_ncbi: Clock, parsing: Clock, interpreting: Clock,
  complete: CheckCircle, failed: XCircle,
};

const STATUS_COLORS: Record<string, string> = {
  queued: 'text-gray-400', submitted_to_ncbi: 'text-teal-500', polling_ncbi: 'text-teal-500',
  parsing: 'text-teal-500', interpreting: 'text-teal-500', complete: 'text-teal-600', failed: 'text-red-500',
};

export default function DashboardPage() {
  const { user, isGuest } = useAuth();
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [usage, setUsage] = useState({ count: 0, limit: 10, remaining: 10 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getJobs(), getJobCount()])
      .then(([j, u]) => { setJobs(j); setUsage(u); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const recentJobs = jobs.slice(0, 5);
  const completedCount = jobs.filter(j => j.status === 'complete').length;
  const failedCount = jobs.filter(j => j.status === 'failed').length;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-teal-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          {isGuest ? 'Welcome to Bio Nexus' : `Welcome back${user?.user_metadata?.full_name ? `, ${user.user_metadata.full_name.split(' ')[0]}` : ''}`}
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          {isGuest ? 'You\'re using as a guest. ' : ''}
          {usage.remaining} of {usage.limit} daily analyses remaining
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { icon: BarChart3, label: 'Total Jobs', value: jobs.length, color: 'text-teal-600', bg: 'bg-teal-50' },
          { icon: CheckCircle, label: 'Completed', value: completedCount, color: 'text-teal-600', bg: 'bg-teal-50' },
          { icon: TrendingUp, label: 'Today', value: usage.count, color: 'text-blue-600', bg: 'bg-blue-50' },
          { icon: XCircle, label: 'Failed', value: failedCount, color: 'text-red-500', bg: 'bg-red-50' },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-gray-200 p-4">
            <div className={`w-8 h-8 ${s.bg} rounded-lg flex items-center justify-center mb-2`}>
              <s.icon className={`w-4 h-4 ${s.color}`} />
            </div>
            <div className="text-2xl font-bold text-gray-900">{s.value}</div>
            <div className="text-xs text-gray-500">{s.label}</div>
          </div>
        ))}
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Recent Activity</h2>
          {jobs.length > 0 && (
            <Link href="/jobs" className="text-sm text-teal-600 hover:text-teal-700 font-medium">
              View all
            </Link>
          )}
        </div>

        {recentJobs.length > 0 ? (
          <div className="space-y-3">
            {recentJobs.map((job) => {
              const Icon = STATUS_ICONS[job.status] || Clock;
              const color = STATUS_COLORS[job.status] || 'text-gray-400';
              const label = job.current_step_label || STEP_LABELS[job.status as keyof typeof STEP_LABELS] || job.status;
              return (
                <Link
                  key={job.id}
                  href={`/jobs/${job.id}`}
                  className="block bg-white rounded-xl border border-gray-200 p-4 hover:border-teal-300 hover:shadow-sm transition"
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${job.status === 'complete' ? 'bg-teal-50' : job.status === 'failed' ? 'bg-red-50' : 'bg-gray-50'}`}>
                      <Icon className={`w-4 h-4 ${color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{label}</p>
                      {job.context_json?.query?.sequence && (
                        <p className="text-xs text-gray-500 truncate mt-0.5">{job.context_json.query.sequence.slice(0, 80)}...</p>
                      )}
                    </div>
                    <div className="text-xs text-gray-400 shrink-0">
                      {new Date(job.created_at || Date.now()).toLocaleDateString()}
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        ) : (
          <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
            <Dna className="w-12 h-12 text-gray-200 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Run your first analysis</h3>
            <p className="text-sm text-gray-500 mb-6">Submit a protein sequence to BLAST, get annotations, structure data, and AI-powered interpretation.</p>
            <Link
              href="/analyze"
              className="inline-flex items-center gap-2 px-6 py-3 bg-teal-600 text-white text-sm font-medium rounded-xl hover:bg-teal-700 transition"
            >
              <Play className="w-4 h-4" />
              Start Analysis
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
