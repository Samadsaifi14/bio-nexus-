'use client';

import { useState } from 'react';
import type { BlastHitSummary } from '@/types/pipeline';

interface AlignmentViewProps {
  hit: BlastHitSummary;
}

const COLORS: Record<string, string> = {
  A: 'text-green-700',
  R: 'text-blue-700',
  N: 'text-purple-700',
  D: 'text-red-700',
  C: 'text-yellow-700',
  Q: 'text-indigo-700',
  E: 'text-red-700',
  G: 'text-gray-700',
  H: 'text-blue-700',
  I: 'text-green-700',
  L: 'text-green-700',
  K: 'text-blue-700',
  M: 'text-green-700',
  F: 'text-green-700',
  P: 'text-orange-700',
  S: 'text-teal-700',
  T: 'text-teal-700',
  W: 'text-green-700',
  Y: 'text-blue-700',
  V: 'text-green-700',
};

function colorChar(c: string): string {
  return COLORS[c.toUpperCase()] || 'text-gray-700';
}

function renderLine(label: string, seq: string, start: number, isMidline: boolean = false): JSX.Element {
  const chars = seq.split('');
  const groups: JSX.Element[] = [];
  for (let i = 0; i < chars.length; i += 60) {
    const chunk = chars.slice(i, i + 60);
    groups.push(
      <div key={i} className="flex font-mono text-xs leading-5">
        <span className="w-12 text-right text-gray-400 shrink-0 mr-2">{start + i}</span>
        <span className="tracking-wider">
          {chunk.map((c, j) => (
            <span key={j} className={isMidline ? (c === '|' ? 'text-teal-600 font-bold' : 'text-gray-300') : colorChar(c)}>
              {c}
            </span>
          ))}
        </span>
        <span className="w-12 text-left text-gray-400 shrink-0 ml-2">{start + i + chunk.length}</span>
      </div>
    );
  }
  return (
    <div className="mb-1">
      <span className="inline-block w-8 text-xs text-gray-400 font-mono shrink-0">{label}</span>
      <div className="inline-block">{groups}</div>
    </div>
  );
}

export function AlignmentView({ hit }: AlignmentViewProps) {
  const [showAll, setShowAll] = useState(false);

  if (!hit.query_alignment || !hit.hit_alignment) {
    return null;
  }

  const qSeq = hit.query_alignment;
  const hSeq = hit.hit_alignment;
  const mid = hit.midline || '';
  const alignLen = hit.alignment_length || qSeq.length;
  const identities = mid.split('').filter(c => c === '|').length;
  const pctId = alignLen > 0 ? Math.round((identities / alignLen) * 100) : 0;
  const positives = hit.positive || 0;
  const gaps = hit.gaps || 0;

  const totalLines = Math.ceil(qSeq.length / 60);
  const displayLines = showAll ? totalLines : Math.min(totalLines, 3);

  const truncate = (seq: string, lines: number) => seq.slice(0, lines * 60);
  const displayQ = showAll ? qSeq : truncate(qSeq, displayLines);
  const displayH = showAll ? hSeq : truncate(hSeq, displayLines);
  const displayM = showAll ? mid : truncate(mid, displayLines);

  return (
    <div className="mt-3 pt-3 border-t border-gray-100">
      <div className="flex items-center gap-4 mb-3 text-xs text-gray-500">
        <span>Identities: <strong className="text-gray-900">{identities}/{alignLen} ({pctId}%)</strong></span>
        <span>Positives: <strong className="text-gray-900">{positives}</strong></span>
        {gaps > 0 && <span>Gaps: <strong className="text-gray-900">{gaps}</strong></span>}
      </div>

      <div className="bg-gray-50 rounded-lg p-3 overflow-x-auto">
        {renderLine('Query', displayQ, hit.query_from || 0)}
        {renderLine('', displayM, 0, true)}
        {renderLine('Sbjct', displayH, hit.hit_from || 0)}
      </div>

      {!showAll && totalLines > 3 && (
        <button
          onClick={() => setShowAll(true)}
          className="mt-2 text-xs text-teal-600 hover:text-teal-700"
        >
          Show full alignment ({totalLines} lines)
        </button>
      )}
    </div>
  );
}
