'use client';

import { Dna } from 'lucide-react';
import { STEP_LABELS } from '@/types/pipeline';
import type { JobStepStatus } from '@/types/pipeline';

interface JobProgressProps {
  stepsCompleted: string[];
  status: string;
}

const STATUS_ORDER: JobStepStatus[] = [
  'queued',
  'submitted_to_ncbi',
  'polling_ncbi',
  'parsing',
  'interpreting',
  'complete',
];

export default function JobProgress({ stepsCompleted, status }: JobProgressProps) {
  const currentIdx = STATUS_ORDER.findIndex((s) => s === status);
  const isComplete = status === 'complete';
  const isFailed = status === 'failed';

  if (isComplete) return null;

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="relative w-10 h-10">
          <div className="absolute inset-0 rounded-full bg-teal-500/20 animate-ping" />
          <div className="relative w-10 h-10 rounded-full bg-teal-500 flex items-center justify-center">
            <Dna className="w-5 h-5 text-white" />
          </div>
        </div>
        <div>
          <p className="font-medium text-gray-900">
            {STEP_LABELS[status as JobStepStatus] || 'Processing...'}
          </p>
          <p className="text-xs text-gray-500">
            Usually 30s–3min depending on NCBI load
          </p>
        </div>
      </div>

      <div className="space-y-2">
        {STATUS_ORDER.slice(1, -1).map((s, i) => {
          const stepIdx = i + 1;
          const isActive = currentIdx === stepIdx;
          const isDone = currentIdx > stepIdx;
          return (
            <div key={s} className="flex items-center gap-3">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${
                isDone ? 'bg-teal-500' : isActive ? 'bg-teal-500/20 border-2 border-teal-500' : 'bg-gray-100'
              }`}>
                {isDone && <span className="text-white text-xs">✓</span>}
              </div>
              <span className={`text-sm ${isActive ? 'font-medium text-gray-900' : isDone ? 'text-gray-500' : 'text-gray-400'}`}>
                {STEP_LABELS[s]}
              </span>
              {isActive && (
                <span className="w-2 h-2 rounded-full bg-teal-500 animate-pulse ml-auto" />
              )}
            </div>
          );
        })}
      </div>

      {isFailed && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl">
          <p className="text-sm text-red-700 font-medium">Pipeline failed</p>
        </div>
      )}
    </div>
  );
}
