'use client';

import { CheckCircle2, XCircle } from 'lucide-react';

interface Step {
  name: string;
  label: string;
}

const STEPS: Step[] = [
  { name: 'blast', label: 'BLAST search' },
  { name: 'uniprot', label: 'UniProt annotations' },
  { name: 'alphafold', label: 'AlphaFold structure' },
];

interface JobProgressProps {
  stepsCompleted: string[];
  status: string;
}

export default function JobProgress({ stepsCompleted, status }: JobProgressProps) {
  const isComplete = status === 'complete';
  const isFailed = status === 'failed';
  const stepSet = new Set(stepsCompleted);
  const pct = stepsCompleted.length === 0 ? 0 : Math.round((stepsCompleted.length / STEPS.length) * 100);

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-900">Pipeline progress</h3>
        <span className="text-xs text-gray-500">{pct}%</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-1.5 mb-5">
        <div
          className={`h-1.5 rounded-full transition-all duration-500 ${isFailed ? 'bg-error' : 'bg-accent'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="space-y-3">
        {STEPS.map((step) => {
          const done = stepSet.has(step.name);
          const active = status === 'running' && (step.name === stepsCompleted[stepsCompleted.length - 1] || (!done && stepsCompleted.length === 0 && step.name === STEPS[0].name));
          return (
            <div key={step.name} className="flex items-center gap-3">
              {done ? (
                <CheckCircle2 className="w-5 h-5 text-teal-600 shrink-0" />
              ) : isFailed ? (
                <XCircle className="w-5 h-5 text-red-500 shrink-0" />
              ) : active ? (
                <div className="w-5 h-5 rounded-full bg-accent animate-pulse shrink-0" />
              ) : (
                <div className="w-5 h-5 rounded-full border-2 border-gray-300 shrink-0" />
              )}
              <span className={`text-sm ${done ? 'text-gray-900 font-medium' : active ? 'text-teal-700' : 'text-gray-400'}`}>
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
      {isComplete && (
        <p className="text-xs text-accent mt-3 font-medium">All steps complete</p>
      )}
      {isFailed && (
        <p className="text-xs text-red-500 mt-3 font-medium">Pipeline failed</p>
      )}
    </div>
  );
}
