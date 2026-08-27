'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GitBranch, Clock, CheckCircle, XCircle } from '@phosphor-icons/react';
import { getJobGraph, type JobNode, type JobGraph } from '@/lib/api';
import { STEP_LABELS, type JobStepStatus } from '@/types/pipeline';

const STATUS_ICON: Record<string, typeof Clock> = {
  complete: CheckCircle,
  failed: XCircle,
  running: Clock,
  queued: Clock,
};

const STATUS_COLOR: Record<string, string> = {
  complete: 'text-emerald-400',
  failed: 'text-red-400',
  running: 'text-blue-400',
  queued: 'text-gray-400',
};

function statusLabel(status: string): string {
  return STEP_LABELS[status as JobStepStatus] || status;
}

function timeAgo(iso: string | null): string {
  if (!iso) return '';
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

interface JobGraphProps {
  jobId: string;
  onNodeClick?: (jobId: string) => void;
  onBranch?: (jobId: string) => void;
}

export function JobGraph({ jobId, onNodeClick, onBranch }: JobGraphProps) {
  const [graph, setGraph] = useState<JobGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getJobGraph(jobId)
      .then(setGraph)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [jobId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500 py-4">
        <GitBranch className="w-4 h-4 animate-pulse" />
        Loading history graph...
      </div>
    );
  }

  if (error || !graph) {
    return null;
  }

  const nodeMap = new Map(graph.nodes.map((n) => [n.id, n]));
  const sorted = topologicalSort(graph);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400 mb-3">
        <GitBranch className="w-4 h-4" />
        Job History Graph
      </div>
      <div className="relative pl-4">
        <div className="absolute left-[11px] top-2 bottom-2 w-px bg-gray-200 dark:bg-gray-700" />
        <AnimatePresence mode="popLayout">
          {sorted.map((nodeId, i) => {
            const node = nodeMap.get(nodeId);
            if (!node) return null;
            const Icon = STATUS_ICON[node.status] || Clock;
            const color = STATUS_COLOR[node.status] || 'text-gray-400';
            const isFocus = node.id === jobId;
            return (
              <motion.div
                key={node.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ delay: i * 0.05 }}
                className={`relative flex items-center gap-3 py-2 px-3 rounded-lg cursor-pointer transition-colors mb-1 ${
                  isFocus
                    ? 'bg-blue-50 dark:bg-blue-900/20 ring-1 ring-blue-200 dark:ring-blue-800'
                    : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'
                }`}
                onClick={() => onNodeClick?.(node.id)}
              >
                <div className="relative z-10 -ml-4">
                  <div className={`w-[22px] h-[22px] rounded-full border-2 bg-white dark:bg-gray-900 flex items-center justify-center ${
                    isFocus ? 'border-blue-500' : 'border-gray-300 dark:border-gray-600'
                  }`}>
                    <Icon className={`w-3 h-3 ${color}`} />
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">{node.query_preview || 'Pipeline run'}</span>
                    {isFocus && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium">
                        THIS
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                    <span>{statusLabel(node.status)}</span>
                    <span>&middot;</span>
                    <span>{timeAgo(node.created_at)}</span>
                  </div>
                </div>
                {!isFocus && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onBranch?.(node.id);
                    }}
                    className="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    Branch from here
                  </button>
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}

function topologicalSort(graph: JobGraph): string[] {
  const visited = new Set<string>();
  const result: string[] = [];
  const nodeIds = new Set(graph.nodes.map((n) => n.id));

  function visit(id: string) {
    if (visited.has(id)) return;
    visited.add(id);
    // Visit parent first (ancestors come before children)
    for (const edge of graph.edges) {
      if (edge.to === id && nodeIds.has(edge.from)) {
        visit(edge.from);
      }
    }
    result.push(id);
  }

  for (const node of graph.nodes) {
    visit(node.id);
  }
  return result;
}
