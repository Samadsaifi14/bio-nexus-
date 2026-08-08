'use client';

import type { MotifMatch } from '@/types/pipeline';

export const TRACK_COLORS = ['#22D3EE', '#A855F7', '#FBBF24', '#FB923C', '#34D399', '#F87171', '#60A5FA', '#E879F9'];

export function MotifTrack({
  length,
  tracks,
}: {
  length: number;
  tracks: Array<{ name: string; matches: MotifMatch[] }>;
}) {
  if (length === 0) return null;
  const W = 1000;
  const ROW_H = 18;
  const headerH = 18;

  const px = (pos: number) => (pos / length) * W;

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${headerH + tracks.length * ROW_H + 6}`} className="w-full min-w-[480px] h-auto" role="img" aria-label="Motif match map">
        {/* sequence backbone */}
        <line x1={0} y1={headerH + 8} x2={W} y2={headerH + 8} stroke="rgba(132,140,164,0.35)" strokeWidth={2} />
        {tracks.map((track, ti) => {
          const color = TRACK_COLORS[ti % TRACK_COLORS.length];
          const y = headerH + ti * ROW_H;
          return (
            <g key={track.name}>
              <text x={0} y={y + 6} fill="#94A3B8" fontSize={11}>
                {track.name}
              </text>
              {track.matches.map((m, mi) => {
                const x = px(m.start - 1);
                const w = Math.max(6, px(m.end - m.start + 1) - px(m.start - 1));
                return (
                  <g key={`${m.start}-${mi}`}>
                    <rect x={x} y={y + 10} width={w} height={6} rx={2} fill={color} opacity={0.9} />
                    <title>{`${track.name}: ${m.start}–${m.end} (${m.motif})`}</title>
                  </g>
                );
              })}
            </g>
          );
        })}
        {/* scale ticks every 10% */}
        {Array.from({ length: 11 }).map((_, i) => (
          <g key={i}>
            <line x1={(i / 10) * W} y1={headerH + tracks.length * ROW_H} x2={(i / 10) * W} y2={headerH + tracks.length * ROW_H + 5} stroke="rgba(132,140,164,0.4)" strokeWidth={1} />
            <text x={(i / 10) * W - 12} y={headerH + tracks.length * ROW_H + 15} fill="#64748B" fontSize={9} textAnchor="middle">
              {Math.round((i / 10) * length)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

export function MatchTable({ matches }: { matches: MotifMatch[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-wider text-text-muted border-b border-glass-border">
            <th className="py-2 pr-4">#</th>
            <th className="py-2 pr-4">Start</th>
            <th className="py-2 pr-4">End</th>
            <th className="py-2">Match</th>
          </tr>
        </thead>
        <tbody>
          {matches.map((m, i) => (
            <tr key={i} className="border-b border-glass-border/60 last:border-0">
              <td className="py-2 pr-4 text-text-muted">{i + 1}</td>
              <td className="py-2 pr-4 font-mono text-accent-cyan">{m.start}</td>
              <td className="py-2 pr-4 font-mono text-accent-cyan">{m.end}</td>
              <td className="py-2 font-mono text-text-secondary">{m.motif}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Inline residue highlighting: the raw protein sequence rendered in 60-residue
 * lines with every match region tinted in its track color. Tracks with an empty
 * match list are ignored; overlapping regions pick the first track's color.
 */
export function SequenceHighlight({
  sequence,
  tracks,
}: {
  sequence: string;
  tracks: Array<{ name: string; matches: MotifMatch[] }>;
}) {
  const colored = tracks
    .map((track, ti) => ({ color: TRACK_COLORS[ti % TRACK_COLORS.length], matches: track.matches }))
    .filter(t => t.matches.length > 0);
  if (colored.length === 0 || sequence.length === 0) return null;

  const LINE = 60;
  const lines: number[] = [];
  for (let s = 0; s < sequence.length; s += LINE) lines.push(s);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {colored.map((t, i) => (
          <span key={i} className="flex items-center gap-1.5 text-[10px] text-text-muted">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: t.color }} />
            {tracks[i].name}
          </span>
        ))}
      </div>
      <div className="overflow-x-auto">
        {lines.map(s => {
          const chunk = sequence.slice(s, s + LINE);
          const runs: Array<{ text: string; color: string | null }> = [];
          for (let k = 0; k < chunk.length; k++) {
            const pos = s + k + 1;
            let color: string | null = null;
            for (const t of colored) {
              if (t.matches.some(m => pos >= m.start && pos <= m.end)) {
                color = t.color;
                break;
              }
            }
            const last = runs[runs.length - 1];
            if (last && last.color === color) last.text += chunk[k];
            else runs.push({ text: chunk[k], color });
          }
          return (
            <div key={s} className="flex items-start gap-3 font-mono text-[11px] leading-5">
              <span className="w-12 shrink-0 text-right text-[9px] text-text-muted pt-1">{s + 1}</span>
              <span className="whitespace-pre bg-surface-0 rounded-md px-2 py-1 text-text-secondary">
                {runs.map((r, i) =>
                  r.color ? (
                    <span key={i} className="rounded-[3px] px-0.5 text-black" style={{ backgroundColor: r.color }}>
                      {r.text}
                    </span>
                  ) : (
                    <span key={i}>{r.text}</span>
                  ),
                )}
              </span>
              <span className="w-12 shrink-0 text-left text-[9px] text-text-muted pt-1">{Math.min(s + LINE, sequence.length)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
