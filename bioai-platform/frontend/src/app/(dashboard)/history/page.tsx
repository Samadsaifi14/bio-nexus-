"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getJobs } from "@/lib/api";
import type { JobStatus } from "@/types/pipeline";

const STATUS_STYLES: Record<string, string> = {
  complete: "bg-teal-100 text-teal-800",
  running:  "bg-blue-100 text-blue-800",
  queued:   "bg-yellow-100 text-yellow-800",
  failed:   "bg-red-100 text-red-800",
};

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
      <div className="p-6 flex items-center gap-2 text-gray-500 text-sm">
        <span className="animate-spin rounded-full h-4 w-4 border-2 border-gray-300 border-t-teal-500" />
        Loading history...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-red-500 text-sm">
        Failed to load history: {error}
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="p-6 text-sm text-gray-500">
        No analyses yet.{" "}
        <a href="/analyze" className="text-teal-600 hover:underline">
          Run your first sequence
        </a>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-xl font-semibold mb-5">Analysis history</h1>
      <div className="rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="px-4 py-3 text-left font-medium text-gray-600 w-28">Job ID</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Pipeline</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600 w-28">Status</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600 hidden sm:table-cell">Created</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr
                key={job.id}
                onClick={() => router.push(`/results/${job.id}`)}
                className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors last:border-0"
              >
                <td className="px-4 py-3 font-mono text-xs text-gray-400">
                  {job.id.slice(0, 8)}...
                </td>
                <td className="px-4 py-3 text-gray-700 capitalize">
                  {(job.pipeline_type ?? "protein_analysis").replace(/_/g, " ")}
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[job.status] ?? "bg-gray-100 text-gray-600"}`}>
                    {job.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-400 text-xs hidden sm:table-cell">
                  {new Date(job.created_at).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
