'use client';

import type { MotifMatch } from '@/types/pipeline';

const TRACK_COLORS = ['#22D3EE', '#A855F7', '#FBBF24', '#FB923C', '#34D399', '#F87171', '#60A5FA', '#E879F9'];

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
