'use client';

import { ChartLine, ChartBar, Dna } from '@phosphor-icons/react';
import type { Ngs2Stage } from '@/lib/api';

type Obj = Record<string, unknown>;
type Point = { x: number; y: number };
type MultiPoint = { x: number; values: Array<{ key: string; y: number }> };

function isObj(value: unknown): value is Obj {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function num(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function stageData(stages: Ngs2Stage[], step: string): Obj | null {
  const stage = stages.find(s => s.step === step);
  return stage && isObj(stage.data) ? stage.data : null;
}

function formatNumber(value: number): string {
  const a = Math.abs(value);
  if (a >= 1_000_000) return `${(value / 1_000_000).toFixed(a >= 10_000_000 ? 0 : 1)}M`;
  if (a >= 1_000) return `${(value / 1_000).toFixed(a >= 10_000 ? 0 : 1)}k`;
  if (a > 0 && a < 0.01) return value.toExponential(2);
  return Number(value.toPrecision(4)).toString();
}

function LineChart({ title, subtitle, points, xLabel, yLabel }: { title: string; subtitle: string; points: Point[]; xLabel: string; yLabel: string }) {
  if (points.length < 2) return null;
  const W = 720, H = 250, L = 58, R = 20, T = 20, B = 46;
  const xs = points.map(p => p.x), ys = points.map(p => p.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  if (maxX - minX <= 1e-12 || maxY - minY <= 1e-12) return null;
  const xPad = (maxX - minX) * 0.02;
  const yPad = (maxY - minY) * 0.08;
  const xa = minX - xPad, xb = maxX + xPad, ya = minY - yPad, yb = maxY + yPad;
  const sx = (x: number) => L + ((x - xa) / (xb - xa)) * (W - L - R);
  const sy = (y: number) => H - B - ((y - ya) / (yb - ya)) * (H - T - B);
  const d = points.map((p, i) => `${i ? 'L' : 'M'} ${sx(p.x).toFixed(2)} ${sy(p.y).toFixed(2)}`).join(' ');
  const ticks = [0, .25, .5, .75, 1];
  return <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
    <div className="mb-3 flex items-start gap-2"><ChartLine className="mt-0.5 h-4 w-4 shrink-0 text-accent-cyan"/><div><p className="text-sm font-semibold text-text-primary">{title}</p><p className="text-[11px] leading-4 text-text-muted">{subtitle}</p></div></div>
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={title}>
      {ticks.map(t => { const y = T + t * (H - T - B); const value = yb - t * (yb - ya); return <g key={`y-${t}`}><line x1={L} x2={W-R} y1={y} y2={y} stroke="currentColor" className="text-white/5"/><text x={L-7} y={y+3} textAnchor="end" fontSize="9" fill="currentColor" className="text-text-muted">{formatNumber(value)}</text></g>; })}
      {ticks.map(t => { const x = L + t * (W - L - R); const value = xa + t * (xb - xa); return <text key={`x-${t}`} x={x} y={H-22} textAnchor="middle" fontSize="9" fill="currentColor" className="text-text-muted">{formatNumber(value)}</text>; })}
      <path d={d} fill="none" stroke="currentColor" strokeWidth="2" className="text-accent-cyan" vectorEffect="non-scaling-stroke"/>
      {points.length <= 120 && points.map((p, i) => <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r="2" fill="currentColor" className="text-accent-cyan"/>)}
      <text x={(L + W - R)/2} y={H-4} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-secondary">{xLabel}</text>
      <text x="12" y={H/2} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-secondary" transform={`rotate(-90 12 ${H/2})`}>{yLabel}</text>
    </svg>
  </div>;
}

function QualityBandChart({ rows }: { rows: Obj[] }) {
  const pts: MultiPoint[] = rows.map(row => {
    const x = num(row.position);
    const mean = num(row.mean), p25 = num(row.p25), p75 = num(row.p75);
    return x === null || mean === null ? null : { x, values: [{ key: 'Mean', y: mean }, ...(p25 === null ? [] : [{ key: 'P25', y: p25 }]), ...(p75 === null ? [] : [{ key: 'P75', y: p75 }])] };
  }).filter((p): p is MultiPoint => !!p);
  if (pts.length < 2) return null;
  const all = pts.flatMap(p => p.values.map(v => v.y));
  const W=720,H=260,L=58,R=20,T=20,B=46;
  const minX=Math.min(...pts.map(p=>p.x)),maxX=Math.max(...pts.map(p=>p.x)),minY=Math.min(...all),maxY=Math.max(...all);
  if(maxX-minX<=1e-12||maxY-minY<=1e-12)return null;
  const yPad=(maxY-minY)*0.08, ya=Math.max(0,minY-yPad), yb=maxY+yPad;
  const sx=(x:number)=>L+((x-minX)/(maxX-minX))*(W-L-R); const sy=(y:number)=>H-B-((y-ya)/(yb-ya))*(H-T-B);
  const series=['Mean','P25','P75'];
  const dFor=(key:string)=>pts.map((p,i)=>{const v=p.values.find(x=>x.key===key); return v ? `${i?'L':'M'} ${sx(p.x).toFixed(2)} ${sy(v.y).toFixed(2)}` : '';}).filter(Boolean).join(' ');
  return <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
    <div className="mb-3 flex items-start gap-2"><ChartLine className="mt-0.5 h-4 w-4 shrink-0 text-accent-cyan"/><div><p className="text-sm font-semibold text-text-primary">Per-base sequencing quality</p><p className="text-[11px] leading-4 text-text-muted">Mean and interquartile-quality estimates by read position, computed from returned FASTQ quality bins.</p></div></div>
    <div className="mb-2 flex flex-wrap gap-3 text-[10px] text-text-muted">{series.map((s,i)=><span key={s}>{i===0?'●':i===1?'○':'◇'} {s}</span>)}</div>
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Per-base sequencing quality">
      {[0,.25,.5,.75,1].map(t=>{const y=T+t*(H-T-B);const value=yb-t*(yb-ya);return <g key={t}><line x1={L} x2={W-R} y1={y} y2={y} stroke="currentColor" className="text-white/5"/><text x={L-7} y={y+3} textAnchor="end" fontSize="9" fill="currentColor" className="text-text-muted">{formatNumber(value)}</text></g>})}
      <path d={dFor('P25')} fill="none" stroke="currentColor" strokeWidth="1.25" strokeDasharray="4 4" className="text-text-muted" vectorEffect="non-scaling-stroke"/>
      <path d={dFor('P75')} fill="none" stroke="currentColor" strokeWidth="1.25" strokeDasharray="2 3" className="text-text-secondary" vectorEffect="non-scaling-stroke"/>
      <path d={dFor('Mean')} fill="none" stroke="currentColor" strokeWidth="2.2" className="text-accent-cyan" vectorEffect="non-scaling-stroke"/>
      <text x={(L+W-R)/2} y={H-4} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-secondary">Read position (bp)</text>
      <text x="12" y={H/2} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-secondary" transform={`rotate(-90 12 ${H/2})`}>Phred quality</text>
    </svg>
  </div>;
}

function BarChart({ title, subtitle, rows, xLabel, yLabel }: { title: string; subtitle: string; rows: Array<{ label: string; value: number }>; xLabel: string; yLabel: string }) {
  if (!rows.length) return null;
  const valid = rows.filter(r => Number.isFinite(r.value));
  if (!valid.length) return null;
  const W=720,H=260,L=64,R=18,T=22,B=70;
  const max=Math.max(...valid.map(r=>r.value),0);
  if(max<=0)return null;
  const step=(W-L-R)/valid.length, bw=Math.max(5,step*0.62), sy=(v:number)=>H-B-(v/max)*(H-T-B);
  return <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
    <div className="mb-3 flex items-start gap-2"><ChartBar className="mt-0.5 h-4 w-4 shrink-0 text-accent-purple"/><div><p className="text-sm font-semibold text-text-primary">{title}</p><p className="text-[11px] leading-4 text-text-muted">{subtitle}</p></div></div>
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={title}>
      {[0,.25,.5,.75,1].map(t=>{const y=T+t*(H-T-B);const value=max*(1-t);return <g key={t}><line x1={L} x2={W-R} y1={y} y2={y} stroke="currentColor" className="text-white/5"/><text x={L-7} y={y+3} textAnchor="end" fontSize="9" fill="currentColor" className="text-text-muted">{formatNumber(value)}</text></g>})}
      {valid.map((r,i)=>{const x=L+i*step+(step-bw)/2;const y=sy(r.value);return <g key={`${r.label}-${i}`}><rect x={x} y={y} width={bw} height={H-B-y} rx="2" fill="currentColor" className="text-accent-purple"/><text x={x+bw/2} y={H-B+14} textAnchor="middle" fontSize="8" fill="currentColor" className="text-text-muted">{r.label.length>14?`${r.label.slice(0,12)}…`:r.label}</text></g>})}
      <text x={(L+W-R)/2} y={H-4} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-secondary">{xLabel}</text>
      <text x="12" y={H/2} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-secondary" transform={`rotate(-90 12 ${H/2})`}>{yLabel}</text>
    </svg>
  </div>;
}

function MetricBars({ data }: { data: Obj }) {
  const pctKeys = [
    ['Mapping rate', data.mapping_rate],
    ['Proper pairs', data.proper_pair_rate],
    ['High MAPQ', data.high_mapq_percent],
    ['Duplicate rate', data.duplicate_rate],
    ['Insert outliers', data.insert_size_outlier_percent],
  ] as const;
  const rows = pctKeys.map(([label,value]) => ({ label, value: num(value) })).filter((r): r is {label:string;value:number} => r.value !== null);
  if (!rows.length) return null;
  return <BarChart title="Alignment QC rates" subtitle="Percentages computed from returned SAM alignment records. Metrics with different units are kept out of this chart." rows={rows} xLabel="Alignment metric" yLabel="Percent (%)"/>;
}

export default function NgsScientificPlots({ stages = [] }: { stages?: Ngs2Stage[] }) {
  if (!Array.isArray(stages) || !stages.length) return null;
  const raw = stageData(stages, 'raw_read_qc');
  const pre = stageData(stages, 'preprocessing');
  const aln = stageData(stages, 'alignment_qc');

  const qualityRows = raw && Array.isArray(raw.quality_by_position) ? raw.quality_by_position.filter(isObj) : [];
  const gcValues = raw && Array.isArray(raw.gc_by_window) ? raw.gc_by_window.map(num).filter((v): v is number => v !== null) : [];
  const gcPoints = gcValues.map((y, i) => ({ x: i + 1, y }));
  const lengthRows = raw && Array.isArray(raw.read_length_distribution) ? raw.read_length_distribution.filter(isObj).map(r => ({ label: String(r.length ?? ''), value: num(r.count) })).filter((r): r is {label:string;value:number} => !!r.label && r.value !== null) : [];
  const coverageRows = aln && isObj(aln.coverage_by_contig) ? Object.entries(aln.coverage_by_contig).map(([label,value]) => ({ label, value: num(value) })).filter((r): r is {label:string;value:number} => r.value !== null) : [];
  const readFlow = pre ? [
    { label: 'Raw', value: num(pre.raw_reads) },
    { label: 'Retained', value: num(pre.retained_reads) },
    { label: 'Discarded', value: num(pre.discarded_reads) },
    { label: 'Adapter-trimmed', value: num(pre.adapter_removed_reads) },
  ].filter((r): r is {label:string;value:number} => r.value !== null) : [];

  const hasAny = qualityRows.length > 1 || gcPoints.length > 1 || lengthRows.length > 0 || readFlow.length > 0 || !!aln || coverageRows.length > 0;
  if (!hasAny) return null;

  return <section className="space-y-4 rounded-xl border border-glass-border bg-surface-0 p-4" aria-label="NGS scientific plots">
    <div className="flex items-start gap-2"><Dna className="mt-0.5 h-5 w-5 shrink-0 text-accent-cyan"/><div><h3 className="text-sm font-semibold text-text-primary">NGS scientific plots</h3><p className="mt-0.5 text-[11px] leading-4 text-text-muted">Visualizations use only measurements returned by this run. Missing, constant or unavailable series are not fabricated.</p></div></div>
    <div className="grid gap-4 xl:grid-cols-2">
      <QualityBandChart rows={qualityRows}/>
      <LineChart title="GC content by sampled read window" subtitle="Window-level GC percentages returned by raw-read QC; useful for spotting composition shifts across the sampled FASTQ stream." points={gcPoints} xLabel="Sampled window" yLabel="GC (%)"/>
      <BarChart title="Read length distribution" subtitle="Observed read counts grouped into the backend's 10 bp length buckets." rows={lengthRows} xLabel="Read length bucket (bp)" yLabel="Read count"/>
      <BarChart title="Read retention through preprocessing" subtitle="Observed read counts before and after trimming/filtering. Adapter-trimmed reads are a subset, not an additive total." rows={readFlow} xLabel="Preprocessing outcome" yLabel="Read count"/>
      {aln && <MetricBars data={aln}/>} 
      <BarChart title="Aligned reference bases by contig" subtitle="Sum of reference-consuming aligned bases per contig after duplicate exclusion. This is not normalized depth or breadth of coverage." rows={coverageRows.slice(0, 20)} xLabel="Contig" yLabel="Aligned reference bases"/>
    </div>
  </section>;
}
