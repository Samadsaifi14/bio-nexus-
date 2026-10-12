'use client';

import { useState, useEffect } from 'react';
import { Wrench, CaretDown, CaretRight, Binary, Globe } from '@phosphor-icons/react';
import { getToolCards, type ToolCard } from '@/lib/api';

const CATEGORY_COLORS: Record<string, string> = {
  sequence_search: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300',
  annotation: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300',
  alignment: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300',
  phylogeny: 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300',
  function: 'bg-pink-100 dark:bg-pink-900/30 text-pink-700 dark:text-pink-300',
  structure: 'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-300',
  analysis: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300',
  network: 'bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300',
  docking: 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300',
  sequencing: 'bg-lime-100 dark:bg-lime-900/30 text-lime-700 dark:text-lime-300',
  simulation: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300',
  pcr: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300',
  drug_discovery: 'bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-300',
};

export function ToolCards() {
  const [tools, setTools] = useState<ToolCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    getToolCards()
      .then(setTools)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400">
        <Wrench className="w-4 h-4" />
        Platform Tools ({tools.length})
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
        {tools.map((tool) => (
          <div
            key={tool.id}
            className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden"
          >
            <button
              onClick={() => setExpanded(expanded === tool.id ? null : tool.id)}
              className="w-full flex items-center gap-2 p-2.5 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
            >
              {expanded === tool.id ? (
                <CaretDown className="w-3 h-3 text-gray-400 shrink-0" />
              ) : (
                <CaretRight className="w-3 h-3 text-gray-400 shrink-0" />
              )}
              <span className="text-sm font-medium truncate">{tool.name}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full ml-auto shrink-0 ${CATEGORY_COLORS[tool.category] || 'bg-gray-100 text-gray-600'}`}>
                {tool.category}
              </span>
            </button>
            {expanded === tool.id && (
              <div className="px-2.5 pb-2.5 space-y-1.5 text-xs text-gray-600 dark:text-gray-400 border-t border-gray-100 dark:border-gray-800">
                <div className="pt-1.5">
                  <span className="font-medium">Version:</span> {tool.version}
                </div>
                <div>
                  <span className="font-medium">External:</span> {tool.external}
                </div>
                {tool.cli_binary && (
                  <div className="flex items-center gap-1">
                    <Binary className="w-3 h-3" />
                    <span>{tool.cli_binary}</span>
                  </div>
                )}
                {tool.api_endpoint && (
                  <div className="flex items-center gap-1">
                    <Globe className="w-3 h-3" />
                    <span className="font-mono text-[10px]">{tool.api_endpoint}</span>
                  </div>
                )}
                <div className="pt-1">
                  <span className="font-medium">Inputs:</span>{' '}
                  {Object.entries(tool.inputs).map(([k, v]) => (
                    <span key={k} className="inline-block mr-2">
                      <span className="font-mono">{k}</span>:<span className="text-gray-400">{v}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
