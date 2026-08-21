'use client';

import { useEffect, useState, useMemo, useCallback, useRef } from 'react';

interface SamRead {
  qname: string;
  flag: number;
  rname: string;
  pos: number;
  mapq: number;
  cigar: string;
  seq: string;
  qual: string;
  isReverse: boolean;
  isUnmapped: boolean;
  isDuplicate: boolean;
  isSecondary: boolean;
}

interface VcfRecord {
  chrom: string;
  pos: number;
  id: string;
  ref: string;
  alt: string;
  qual: number;
  filter: string;
  info: string;
  format?: string;
  sample?: string;
}

interface GenomeViewerProps {
  samUrl?: string;
  vcfUrl?: string;
  referenceUrl?: string;
  locus?: string;
  className?: string;
}

function parseSamFlags(flag: number) {
  return {
    paired: !!(flag & 0x1),
    properPair: !!(flag & 0x2),
    unmapped: !!(flag & 0x4),
    reverse: !!(flag & 0x10),
    secondary: !!(flag & 0x100),
    duplicate: !!(flag & 0x400),
    supplementary: !!(flag & 0x800),
  };
}

function parseSam(text: string): SamRead[] {
  const reads: SamRead[] = [];
  for (const line of text.split('\n')) {
    if (line.startsWith('@') || !line.trim()) continue;
    const cols = line.split('\t');
    if (cols.length < 11) continue;
    const flag = parseInt(cols[1], 10);
    const flags = parseSamFlags(flag);
    if (flags.secondary || flags.supplementary) continue;
    reads.push({
      qname: cols[0],
      flag,
      rname: cols[2],
      pos: parseInt(cols[3], 10),
      mapq: parseInt(cols[4], 10),
      cigar: cols[5],
      seq: cols[9],
      qual: cols[10],
      isReverse: flags.reverse,
      isUnmapped: flags.unmapped,
      isDuplicate: flags.duplicate,
      isSecondary: flags.secondary,
    });
  }
  return reads;
}

function parseCigar(cigar: string): { op: string; len: number }[] {
  const parts: { op: string; len: number }[] = [];
  const re = /(\d+)([MIDNSHP=X])/g;
  let m;
  while ((m = re.exec(cigar)) !== null) {
    parts.push({ op: m[2], len: parseInt(m[1], 10) });
  }
  return parts;
}

function cigarRefLen(cigar: string): number {
  let len = 0;
  for (const { op, len: l } of parseCigar(cigar)) {
    if ('MDN=X'.includes(op)) len += l;
  }
  return len;
}

function parseVcf(text: string): VcfRecord[] {
  const records: VcfRecord[] = [];
  for (const line of text.split('\n')) {
    if (line.startsWith('#') || !line.trim()) continue;
    const cols = line.split('\t');
    if (cols.length < 8) continue;
    records.push({
      chrom: cols[0],
      pos: parseInt(cols[1], 10),
      id: cols[2],
      ref: cols[3],
      alt: cols[4],
      qual: parseFloat(cols[5]) || 0,
      filter: cols[6],
      info: cols[7],
      format: cols[8],
      sample: cols[9],
    });
  }
  return records;
}

function VariantType({ ref, alt }: { ref: string; alt: string }) {
  const alts = alt.split(',');
  if (alts.some(a => a.length > 1 && ref.length > 1)) {
    return <span className="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 text-xs font-mono">MNV</span>;
  }
  if (alts.some(a => a === '.' || a.length === 1)) {
    if (ref.length === 1 && alts.every(a => a.length === 1)) {
      return <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 text-xs font-mono">SNV</span>;
    }
    return <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 text-xs font-mono">INDEL</span>;
  }
  if (alts.some(a => a.length > ref.length)) {
    return <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 text-xs font-mono">INS</span>;
  }
  return <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 text-xs font-mono">DEL</span>;
}

function ReadsTrack({
  reads,
  regionStart,
  regionEnd,
  width,
}: {
  reads: SamRead[];
  regionStart: number;
  regionEnd: number;
  width: number;
}) {
  const ROW_HEIGHT = 16;
  const MARGIN = 2;

  const { blocks, maxRow, coverage } = useMemo(() => {
    const cov = new Array(regionEnd - regionStart + 1).fill(0);
    const placed: { read: SamRead; x: number; w: number; row: number; blocks: { x: number; w: number; isMatch: boolean }[] }[] = [];
    const rowEnd: number[] = [];

    const sorted = reads
      .filter(r => !r.isUnmapped && r.pos < regionEnd && r.pos + cigarRefLen(r.cigar) > regionStart)
      .sort((a, b) => a.pos - b.pos || b.mapq - a.mapq);

    for (const read of sorted) {
      const refLen = cigarRefLen(read.cigar);
      const readStart = Math.max(read.pos, regionStart);
      const readEnd = Math.min(read.pos + refLen, regionEnd);

      for (let i = readStart - regionStart; i <= readEnd - regionStart; i++) {
        if (i >= 0 && i < cov.length) cov[i]++;
      }

      let row = 0;
      while (row < rowEnd.length && rowEnd[row] > read.pos) row++;
      if (row >= rowEnd.length) rowEnd.push(0);
      rowEnd[row] = read.pos + refLen;

      const x = ((read.pos - regionStart) / (regionEnd - regionStart)) * width;
      const w = ((readEnd - readStart) / (regionEnd - regionStart)) * width;

      const blocks: { x: number; w: number; isMatch: boolean }[] = [];
      let refPos = read.pos;
      for (const { op, len } of parseCigar(read.cigar)) {
        if ('MDN=X'.includes(op)) {
          const bStart = Math.max(refPos, regionStart);
          const bEnd = Math.min(refPos + len, regionEnd);
          if (bEnd > bStart) {
            blocks.push({
              x: ((bStart - regionStart) / (regionEnd - regionStart)) * width,
              w: ((bEnd - bStart) / (regionEnd - regionStart)) * width,
              isMatch: op !== 'N',
            });
          }
          refPos += len;
        } else if (op === 'I') {
          // insertion - no ref movement
        } else if (op === 'S') {
          refPos += len;
        } else if (op === 'H') {
          // hard clip
        }
      }

      placed.push({ read, x, w, row, blocks });
    }

    return { blocks: placed, maxRow: rowEnd.length, coverage: cov };
  }, [reads, regionStart, regionEnd, width]);

  const COV_HEIGHT = 60;
  const readsHeight = Math.max(maxRow * (ROW_HEIGHT + MARGIN), 100);
  const totalHeight = COV_HEIGHT + readsHeight + 20;

  const maxCov = Math.max(...coverage, 1);

  return (
    <svg width={width} height={totalHeight} className="font-mono">
      {/* Coverage track */}
      <g>
        <text x={4} y={12} className="fill-text-muted" fontSize={10}>Coverage</text>
        {coverage.map((c, i) => {
          if (c === 0) return null;
          const barH = (c / maxCov) * (COV_HEIGHT - 16);
          return (
            <rect
              key={i}
              x={(i / coverage.length) * width}
              y={COV_HEIGHT - barH}
              width={Math.max(width / coverage.length, 1)}
              height={barH}
              className="fill-accent-cyan/40"
            />
          );
        })}
        {[1, 2, 3, 4, 5].map(n => {
          const v = Math.round((maxCov / 5) * n);
          const y = COV_HEIGHT - (n / 5) * (COV_HEIGHT - 16);
          return (
            <g key={n}>
              <line x1={0} y1={y} x2={width} y2={y} className="stroke-text-muted/20" strokeWidth={0.5} />
              <text x={width - 4} y={y - 2} className="fill-text-muted" fontSize={8} textAnchor="end">{v}x</text>
            </g>
          );
        })}
      </g>

      {/* Reads track */}
      <g transform={`translate(0,${COV_HEIGHT + 4})`}>
        <text x={4} y={12} className="fill-text-muted" fontSize={10}>Reads ({reads.length})</text>
        {blocks.map((b, i) => (
          <g key={i} transform={`translate(0,${16 + b.row * (ROW_HEIGHT + MARGIN)})`}>
            {b.read.isReverse && (
              <polygon
                points={`${b.x - 4},${ROW_HEIGHT / 2} ${b.x + 2},${2} ${b.x + 2},${ROW_HEIGHT - 2}`}
                className="fill-accent-cyan/60"
              />
            )}
            {b.blocks.map((blk, j) => (
              <rect
                key={j}
                x={blk.x}
                y={blk.isMatch ? 2 : 0}
                width={Math.max(blk.w, 1)}
                height={blk.isMatch ? ROW_HEIGHT - 4 : ROW_HEIGHT}
                rx={1}
                className={blk.isMatch ? 'fill-accent-cyan/70' : 'fill-amber-400/80'}
              />
            ))}
          </g>
        ))}
      </g>
    </svg>
  );
}

export default function GenomeViewer({
  samUrl,
  vcfUrl,
  locus,
  className = '',
}: GenomeViewerProps) {
  const [samText, setSamText] = useState('');
  const [vcfText, setVcfText] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [viewStart, setViewStart] = useState(0);
  const [viewEnd, setViewEnd] = useState(1000);
  const [searchLocus, setSearchLocus] = useState(locus || '');
  const [selectedVariant, setSelectedVariant] = useState<VcfRecord | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(800);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver(entries => {
      for (const entry of entries) setContainerWidth(entry.contentRect.width);
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const reads = useMemo(() => samText ? parseSam(samText) : [], [samText]);
  const variants = useMemo(() => vcfText ? parseVcf(vcfText) : [], [vcfText]);

  const parsedLocus = useMemo(() => {
    if (!searchLocus) return null;
    const m = searchLocus.match(/^(\d+|chr\d+|[A-Za-z]+):(\d+)-(\d+)$/i);
    if (m) return { chr: m[1], start: parseInt(m[2], 10), end: parseInt(m[3], 10) };
    const m2 = searchLocus.match(/^(\d+|chr\d+|[A-Za-z]+):(\d+)$/i);
    if (m2) {
      const pos = parseInt(m2[2], 10);
      return { chr: m2[1], start: Math.max(0, pos - 500), end: pos + 500 };
    }
    return null;
  }, [searchLocus]);

  useEffect(() => {
    if (parsedLocus) {
      setViewStart(parsedLocus.start);
      setViewEnd(parsedLocus.end);
    }
  }, [parsedLocus]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError('');
      try {
        const [samRes, vcfRes] = await Promise.allSettled([
          samUrl ? fetch(samUrl).then(r => r.ok ? r.text() : Promise.reject(new Error(`SAM HTTP ${r.status}`))) : Promise.resolve(''),
          vcfUrl ? fetch(vcfUrl).then(r => r.ok ? r.text() : Promise.reject(new Error(`VCF HTTP ${r.status}`))) : Promise.resolve(''),
        ]);
        if (cancelled) return;
        const newSam = samRes.status === 'fulfilled' ? samRes.value : '';
        const newVcf = vcfRes.status === 'fulfilled' ? vcfRes.value : '';
        setSamText(newSam);
        setVcfText(newVcf);
        if (samRes.status === 'rejected' && samUrl) console.warn('[GenomeViewer]', samRes.reason?.message);
        if (vcfRes.status === 'rejected' && vcfUrl) console.warn('[GenomeViewer]', vcfRes.reason?.message);
        if (!parsedLocus && newSam) {
          const parsed = parseSam(newSam);
          if (parsed.length > 0) {
            const minPos = Math.min(...parsed.map(r => r.pos));
            const maxPos = Math.max(...parsed.map(r => r.pos + cigarRefLen(r.cigar)));
            setViewStart(minPos);
            setViewEnd(maxPos);
          }
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [samUrl, vcfUrl]);

  const zoom = useCallback((factor: number) => {
    const mid = (viewStart + viewEnd) / 2;
    const half = ((viewEnd - viewStart) / 2) * factor;
    setViewStart(Math.max(0, Math.floor(mid - half)));
    setViewEnd(Math.ceil(mid + half));
  }, [viewStart, viewEnd]);

  const pan = useCallback((frac: number) => {
    const span = viewEnd - viewStart;
    const shift = Math.floor(span * frac);
    setViewStart(Math.max(0, viewStart + shift));
    setViewEnd(viewEnd + shift);
  }, [viewStart, viewEnd]);

  if (loading) {
    return (
      <div className={`flex items-center justify-center py-12 bg-surface-1 rounded-xl ${className}`}>
        <div className="w-5 h-5 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
        <span className="ml-3 text-sm text-text-muted">Loading genome data...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`p-4 bg-error/5 border border-error/20 rounded-xl ${className}`}>
        <p className="text-sm text-error font-medium">Failed to load genome data</p>
        <p className="text-xs text-error/70 mt-1 font-mono">{error}</p>
      </div>
    );
  }

  const viewSize = viewEnd - viewStart;

  return (
    <div ref={containerRef} className={`space-y-3 ${className}`}>
      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1 bg-surface-1 rounded-lg p-1">
          <button onClick={() => pan(-0.5)} className="px-2 py-1 text-xs rounded hover:bg-surface-2 text-text-muted hover:text-text-primary transition" title="Pan left">
            ←
          </button>
          <button onClick={() => zoom(0.5)} className="px-2 py-1 text-xs rounded hover:bg-surface-2 text-text-muted hover:text-text-primary transition" title="Zoom in">
            + Zoom In
          </button>
          <button onClick={() => zoom(2)} className="px-2 py-1 text-xs rounded hover:bg-surface-2 text-text-muted hover:text-text-primary transition" title="Zoom out">
            − Zoom Out
          </button>
          <button onClick={() => pan(0.5)} className="px-2 py-1 text-xs rounded hover:bg-surface-2 text-text-muted hover:text-text-primary transition" title="Pan right">
            →
          </button>
        </div>
        <input
          type="text"
          value={searchLocus}
          onChange={e => setSearchLocus(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              const m = e.currentTarget.value.match(/^(\d+|chr\d+):(\d+)-(\d+)$/i) || e.currentTarget.value.match(/^(\d+|chr\d+):(\d+)$/i);
              if (m) {
                const pos = parseInt(m[2], 10);
                const end = m[3] ? parseInt(m[3], 10) : pos + 1000;
                setViewStart(Math.max(0, pos - (m[3] ? 0 : 500)));
                setViewEnd(end);
              }
            }
          }}
          placeholder="Locus (e.g. 1:1000-5000)"
          className="px-3 py-1.5 text-xs rounded-lg bg-surface-1 border border-glass-border text-text-primary placeholder-text-muted font-mono flex-1 min-w-[180px]"
        />
        <span className="text-xs text-text-muted font-mono">
          {reads.filter(r => !r.isUnmapped).length} reads · {viewStart.toLocaleString()}–{viewEnd.toLocaleString()} ({(viewSize).toLocaleString()} bp)
        </span>
      </div>

      {/* Reads track */}
      {reads.length > 0 && (
        <div className="bg-surface-1 rounded-xl border border-glass-border p-2 overflow-x-auto">
          <ReadsTrack
            reads={reads}
            regionStart={viewStart}
            regionEnd={viewEnd}
            width={Math.max(containerWidth - 16, 400)}
          />
        </div>
      )}

      {/* Variants table */}
      {variants.length > 0 && (
        <div className="bg-surface-1 rounded-xl border border-glass-border overflow-hidden">
          <div className="px-3 py-2 border-b border-glass-border">
            <h4 className="text-xs font-semibold text-text-primary">Variants ({variants.length})</h4>
          </div>
          <div className="overflow-x-auto max-h-[300px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-surface-2">
                <tr className="text-text-muted text-left">
                  <th className="px-3 py-2 font-medium">Position</th>
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 font-medium">Ref</th>
                  <th className="px-3 py-2 font-medium">Alt</th>
                  <th className="px-3 py-2 font-medium">Quality</th>
                  <th className="px-3 py-2 font-medium">Filter</th>
                  <th className="px-3 py-2 font-medium">Info</th>
                </tr>
              </thead>
              <tbody>
                {variants.map((v, i) => (
                  <tr
                    key={i}
                    className={`border-t border-glass-border cursor-pointer transition-colors ${
                      selectedVariant === v ? 'bg-accent-cyan/10' : 'hover:bg-surface-2'
                    }`}
                    onClick={() => {
                      setSelectedVariant(selectedVariant === v ? null : v);
                      setSearchLocus(`${v.chrom}:${v.pos}`);
                      setViewStart(Math.max(0, v.pos - 200));
                      setViewEnd(v.pos + 200);
                    }}
                  >
                    <td className="px-3 py-2 font-mono text-text-primary">{v.chrom}:{v.pos.toLocaleString()}</td>
                    <td className="px-3 py-2"><VariantType ref={v.ref} alt={v.alt} /></td>
                    <td className="px-3 py-2 font-mono text-text-primary">{v.ref}</td>
                    <td className="px-3 py-2 font-mono text-accent-cyan">{v.alt}</td>
                    <td className="px-3 py-2 font-mono text-text-muted">{v.qual > 0 ? v.qual.toFixed(1) : '—'}</td>
                    <td className="px-3 py-2">
                      <span className={`px-1.5 py-0.5 rounded text-xs ${
                        v.filter === 'PASS' ? 'bg-green-500/20 text-green-400' : 'bg-surface-2 text-text-muted'
                      }`}>{v.filter}</span>
                    </td>
                    <td className="px-3 py-2 font-mono text-text-muted max-w-[200px] truncate">{v.info}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {selectedVariant && (
            <div className="px-3 py-2 border-t border-glass-border bg-surface-2">
              <div className="text-xs space-y-1">
                <p className="text-text-primary font-medium">Variant Detail</p>
                <p className="text-text-muted font-mono">
                  {selectedVariant.chrom}:{selectedVariant.pos} {selectedVariant.ref}→{selectedVariant.alt}
                </p>
                <p className="text-text-muted font-mono text-[10px]">
                  INFO: {selectedVariant.info}
                  {selectedVariant.format && selectedVariant.sample && (
                    <> · FORMAT: {selectedVariant.format} · SAMPLE: {selectedVariant.sample}</>
                  )}
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {reads.length === 0 && variants.length === 0 && !loading && (
        <div className="text-center py-8 text-text-muted text-sm">
          No alignment or variant data to display.
        </div>
      )}
    </div>
  );
}
