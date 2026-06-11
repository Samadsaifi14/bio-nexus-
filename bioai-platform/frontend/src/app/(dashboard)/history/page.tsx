'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Clock, Database, Trash2, Loader2, Play, Share2, ChevronDown, ChevronUp, Dna } from 'lucide-react';
import toast from 'react-hot-toast';
import type { JobStatus } from '@/types/pipeline';
import { getJobs, deleteJob } from '@/lib/api';

function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return date.toLocaleDateString();
}

export default function HistoryPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedJob, setExpandedJob] = useState<string | null>(null);

  const fetchJobs = async () => {
    try {
      const data = await getJobs();
      setJobs(data);
    } catch {
      toast.error('Failed to load history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchJobs(); }, []);

  const handleDelete = async (id: string) => {
    try {
      await deleteJob(id);
      setJobs((prev) => prev.filter((j) => j.id !== id));
      toast.success('Job deleted');
    } catch {
      toast.error('Failed to delete job');
    }
  };

  const handleView = (job: JobStatus) => {
    if (job.context_json) {
      router.push(`/dashboard/results/${job.id}`);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Job History</h1>
      <p className="text-gray-600 mb-8">View and manage your past analyses</p>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 text-green-600 animate-spin" />
        </div>
      ) : jobs.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200 p-16 text-center">
          <Dna className="w-16 h-16 text-gray-200 mx-auto mb-6" />
          <h3 className="text-xl font-semibold text-gray-900 mb-3">No analyses yet</h3>
          <p className="text-sm text-gray-500 mb-6 max-w-sm mx-auto">
            Run your first protein analysis to see results here.
          </p>
          <button
            onClick={() => router.push('/dashboard/analyze')}
            className="px-5 py-2.5 bg-green-600 text-white text-sm font-medium rounded-xl hover:bg-green-700 transition"
          >
            Run Analysis
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <div key={job.id} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
                    <Database className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-900 capitalize">{job.pipeline_type?.replace(/_/g, ' ') || 'Pipeline'}</p>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        job.status === 'complete' ? 'bg-green-50 text-green-700' :
                        job.status === 'failed' ? 'bg-red-50 text-red-700' :
                        'bg-yellow-50 text-yellow-700'
                      }`}>
                        {job.status}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 font-mono mt-0.5">{job.query_preview?.slice(0, 60)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 mr-2">{timeAgo(job.created_at)}</span>
                  {job.context_json && (
                    <button onClick={() => handleView(job)} className="p-2 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded-lg transition" title="View results">
                      <Play className="w-4 h-4" />
                    </button>
                  )}
                  <button onClick={() => setExpandedJob(expandedJob === job.id ? null : job.id)} className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-50 rounded-lg transition">
                    {expandedJob === job.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                  <button onClick={() => handleDelete(job.id)} className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition" title="Delete">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              {expandedJob === job.id && (
                <div className="px-5 py-4 border-t border-gray-100 bg-gray-50">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div><span className="text-gray-500">Pipeline:</span> <span className="font-medium">{job.pipeline_type}</span></div>
                    <div><span className="text-gray-500">Created:</span> <span>{new Date(job.created_at).toLocaleString()}</span></div>
                    <div><span className="text-gray-500">Status:</span> <span className="font-medium">{job.status}</span></div>
                    {job.completed_at && <div><span className="text-gray-500">Completed:</span> <span>{new Date(job.completed_at).toLocaleString()}</span></div>}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
