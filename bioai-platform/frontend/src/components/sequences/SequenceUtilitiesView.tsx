'use client';

import { useState } from 'react';
import { Copy, Check } from '@phosphor-icons/react';
import type { SequenceUtilitiesResult } from '@/types/pipeline';

function StatChip({ label, value, valueClass = 'text-text-primary' }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-3 rounded-lg bg-surface-0 border border-glass-border min-w-[96px]">
      <span className="text-[10px] uppercase tracking-wider text-text-muted">{label}</span>
      <span className={`text-lg font-bold font-mono mt-0.5 ${valueClass}`}>{value}</span>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-xs text-text-secondary hover:text-accent-cyan transition flex items-center gap-1.5"
      aria-label="Copy to clipboard"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-accent-cyan" /> : <Copy className="w-3.5 h-3.5" />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

function CompositionBars({ comp }: { comp: NonNullable<SequenceUtilitiesResult['aa_composition']> }) {
  const max = Math.max(...comp.map(c => c.count));
  return (
    <div className="space-y-1.5">
      {comp.map(c => (
        <div key={c.aa} className="flex items-center gap-2">
          <span className="w-6 text-right font-mono text-[11px] text-accent-cyan">{c.aa}</span>
          <div className="flex-1 h-2 rounded-full bg-surface-1 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-accent-cyan/40 to-accent-cyan/90"
              style={{ width: `${Math.max(2, (c.count / max) * 100)}%` }}
            />
          </div>
          <span className="w-8 text-right text-[11px] font-mono text-text-muted">{c.count}</span>
          <span className="w-12 text-right text-[11px] font-mono text-text-muted">{c.pct}%</span>
        </div>
      ))}
    </div>
  );
}

export function SequenceUtilitiesView({ result }: { result: SequenceUtilitiesResult }) {
  const isNuc = result.sequence_type === 'dna' || result.sequence_type === 'rna';
  const typeColor =
    result.sequence_type === 'dna' ? 'text-accent-cyan' :
    result.sequence_type === 'rna' ? 'text-accent-purple' :
    result.sequence_type === 'protein' ? 'text-accent-amber' : 'text-text-muted';

  return (
    <div className="space-y-4">
      {result.issues.length > 0 && (
        <div className="rounded-lg bg-accent-amber/10 border border-accent-amber/30 px-4 py-3 text-xs text-accent-amber">
          {result.issues.map((issue, i) => (
            <p key={i}>{issue}</p>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <StatChip label="Type" value={result.sequence_type.toUpperCase()} valueClass={typeColor} />
        <StatChip label="Length" value={String(result.length)} valueClass="text-accent-cyan" />
        {result.gc_content !== null && (
          <StatChip label="GC content" value={`${result.gc_content}%`} valueClass="text-accent-purple" />
        )}
        {result.molecular_weight !== null && (
          <StatChip label="Mol. weight" value={`${result.molecular_weight.toLocaleString()} Da`} valueClass="text-text-primary" />
        )}
      </div>

      {isNuc && result.reverse_complement && (
        <div className="data-card p-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-text-primary">Reverse complement</h3>
            <CopyButton text={result.reverse_complement} />
          </div>
          <pre className="font-mono text-xs text-text-secondary bg-surface-0 rounded-xl p-3 overflow-x-auto whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
            {result.reverse_complement}
          </pre>
        </div>
      )}

      {result.translation && (
        <div className="data-card p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-2">Translation (forward frames)</h3>
          {result.translation.best && (
            <div className="mb-3 rounded-lg bg-accent-cyan/10 border border-accent-cyan/30 px-3 py-2 text-xs text-text-secondary">
              Best ORF — frame <strong className="text-accent-cyan">{result.translation.best.frame}</strong>, starts at residue{' '}
              <strong className="text-accent-cyan">{result.translation.best.start}</strong>, {result.translation.best.length} aa
              {result.translation.best.has_stop ? ' (ends at a stop codon)' : ' (runs to the sequence end)'}.
            </div>
          )}
          {(() => {
            const translation = result.translation;
            if (!translation) return null;
            return (
          <div className="space-y-2">
            {Object.entries(translation.frames).map(([frame, protein]) => (
              <div key={frame}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] uppercase tracking-wider text-text-muted">Frame {frame}</span>
                  {translation.best?.frame === Number(frame) && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan font-medium">
                      longest ORF
                    </span>
                  )}
                </div>
                <pre className="font-mono text-xs text-text-secondary bg-surface-0 rounded-lg p-2.5 overflow-x-auto whitespace-pre-wrap break-all">
                  {protein || '(too short to translate)'}
                </pre>
              </div>
            ))}
          </div>
            );
          })()}
        </div>
      )}

      {result.aa_composition && result.aa_composition.length > 0 && (
        <div className="data-card p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-3">
            Amino-acid composition ({result.translation ? 'translated CDS' : 'protein'})
          </h3>
          <CompositionBars comp={result.aa_composition} />
        </div>
      )}

      {result.restriction_sites && result.restriction_sites.length > 0 && (
        <div className="data-card p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-3">
            Restriction sites ({result.restriction_sites.length} enzymes)
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[10px] uppercase tracking-wider text-text-muted border-b border-glass-border">
                  <th className="py-2 pr-4">Enzyme</th>
                  <th className="py-2 pr-4">Site</th>
                  <th className="py-2 pr-4">Sites</th>
                  <th className="py-2">Positions (1-based)</th>
                </tr>
              </thead>
              <tbody>
                {result.restriction_sites.map(site => (
                  <tr key={site.name} className="border-b border-glass-border-soft last:border-0">
                    <td className="py-2 pr-4 font-semibold text-accent-cyan">{site.name}</td>
                    <td className="py-2 pr-4 font-mono text-text-secondary">{site.recognition}</td>
                    <td className="py-2 pr-4 font-mono text-text-secondary">{site.count}</td>
                    <td className="py-2 font-mono text-text-muted">
                      {site.positions.slice(0, 12).join(', ')}
                      {site.positions.length > 12 ? ` … +${site.positions.length - 12}` : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
