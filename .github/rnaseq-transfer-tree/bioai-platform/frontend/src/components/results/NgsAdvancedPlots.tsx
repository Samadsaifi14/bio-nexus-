'use client';

import { ChartScatter, GridFour, ChartBar } from '@phosphor-icons/react';
import type { Ngs2Stage } from '@/lib/api';

type Obj = Record<string, unknown>;
type Variant = { chrom: string; pos: number; ref: string; alt: string; dp?: number; af?: number; qual?: number; genotype_quality?: number; type?: string; qc?: Obj };
type HeatRow = { label: string; values: Array<{ key: string; value: number }> };
type Point = { x: number; y: number };
type BarRow = { label: string; value: number };

function isObj(v: unknown): v is Obj { return !!v && typeof v === 'object' && !Array.isArray(v); }
function n(v: unknown): number | null { return typeof v === 'number' && Number.isFinite(v) ? v : null; }
function stageData(stages: Ngs2Stage[], step: string): Obj | null {
  const stage = stages.find(s => s.step === step);
  return stage && isObj(stage.data) ? stage.data : null;
}
function numericEntries(value: Obj): Array<{ key: string; value: number }> {
  return Object.entries(value).flatMap(([key, raw]) => {
    const parsed = n(raw);
    return parsed === null ? [] : [{ key, value: parsed }];
  });
}
function asVariants(value: unknown): Variant[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isObj).flatMap(v => {
    const chrom = String(v.chrom ?? v.contig ?? '');
    const pos = Number(v.pos ?? v.position ?? 0);
    const ref = String(v.ref ?? '');
    const alt = String(v.alt ?? '');
    if (!chrom || !Number.isFinite(pos) || pos <= 0 || !ref || !alt) return [];
    return [{
      chrom, pos, ref, alt,
      dp: n(v.dp) ?? n(v.depth) ?? undefined,
      af: n(v.af) ?? n(v.allele_fraction) ?? n(v.vaf) ?? undefined,
      qual: n(v.qual) ?? n(v.quality) ?? undefined,
      genotype_quality: n(v.genotype_quality) ?? n(v.gq) ?? undefined,
      type: typeof v.type === 'string' ? v.type : undefined,
      qc: isObj(v.qc) ? v.qc : undefined,
    }];
  });
}
function getVariants(stages: Ngs2Stage[]): Variant[] {
  const qc = stageData(stages, 'variant_qc');
  if (qc && Array.isArray(qc.variants)) return asVariants(qc.variants);
  const call = stageData(stages, 'variant_calling');
  if (call && Array.isArray(call.variants)) return asVariants(call.variants);
  return [];
}
function fmt(v: number): string {
  const a = Math.abs(v);
  if (a >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${(v / 1e3).toFixed(1)}k`;
  if (a > 0 && a < 0.01) return v.toExponential(2);
  return Number(v.toPrecision(4)).toString();
}

function Scatter({ title, subtitle, points, xLabel, yLabel }: { title: string; subtitle: string; points: Point[]; xLabel: string; yLabel: string }) {
  if (points.length < 2) return null;
  const W=720,H=260,L=62,R=18,T=22,B=46;
  const xs=points.map(p=>p.x), ys=points.map(p=>p.y);
  const xmin=Math.min(...xs), xmax=Math.max(...xs), ymin=Math.min(...ys), ymax=Math.max(...ys);
  if (xmax-xmin<=1e-12 || ymax-ymin<=1e-12) return null;
  const xpad=(xmax-xmin)*0.05, ypad=(ymax-ymin)*0.08;
  const xa=xmin-xpad, xb=xmax+xpad, ya=ymin-ypad, yb=ymax+ypad;
  const sx=(x:number)=>L+((x-xa)/(xb-xa))*(W-L-R);
  const sy=(y:number)=>H-B-((y-ya)/(yb-ya))*(H-T-B);
  return <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
    <div className="mb-3 flex items-start gap-2"><ChartScatter className="mt-0.5 h-4 w-4 shrink-0 text-accent-cyan"/><div><p className="text-sm font-semibold text-text-primary">{title}</p><p className="text-[11px] leading-4 text-text-muted">{subtitle}</p></div></div>
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={title}>
      {[0,.25,.5,.75,1].map(t=>{const y=T+t*(H-T-B);const value=yb-t*(yb-ya);return <g key={`y-${t}`}><line x1={L} x2={W-R} y1={y} y2={y} stroke="currentColor" className="text-white/5"/><text x={L-7} y={y+3} textAnchor="end" fontSize="9" fill="currentColor" className="text-text-muted">{fmt(value)}</text></g>})}
      {[0,.25,.5,.75,1].map(t=>{const x=L+t*(W-L-R);const value=xa+t*(xb-xa);return <text key={`x-${t}`} x={x} y={H-22} textAnchor="middle" fontSize="9" fill="currentColor" className="text-text-muted">{fmt(value)}</text>})}
      {points.slice(0,1500).map((p,i)=><circle key={i} cx={sx(p.x)} cy={sy(p.y)} r="2.4" fill="currentColor" className="text-accent-cyan" opacity="0.75"/>)}
      <text x={(L+W-R)/2} y={H-4} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-secondary">{xLabel}</text>
      <text x="12" y={H/2} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-secondary" transform={`rotate(-90 12 ${H/2})`}>{yLabel}</text>
    </svg>
  </div>;
}

function Bars({ title, subtitle, rows, yLabel }: { title: string; subtitle: string; rows: BarRow[]; yLabel: string }) {
  const valid=rows.filter(r=>Number.isFinite(r.value)); if(!valid.length) return null;
  const max=Math.max(...valid.map(r=>r.value)); if(max<=0) return null;
  const W=720,H=260,L=64,R=18,T=22,B=74, step=(W-L-R)/valid.length, bw=Math.max(4,step*0.62);
  const sy=(v:number)=>H-B-(v/max)*(H-T-B);
  return <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
    <div className="mb-3 flex items-start gap-2"><ChartBar className="mt-0.5 h-4 w-4 shrink-0 text-accent-purple"/><div><p className="text-sm font-semibold text-text-primary">{title}</p><p className="text-[11px] leading-4 text-text-muted">{subtitle}</p></div></div>
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={title}>
      {[0,.25,.5,.75,1].map(t=>{const y=T+t*(H-T-B);return <g key={t}><line x1={L} x2={W-R} y1={y} y2={y} stroke="currentColor" className="text-white/5"/><text x={L-7} y={y+3} textAnchor="end" fontSize="9" fill="currentColor" className="text-text-muted">{fmt(max*(1-t))}</text></g>})}
      {valid.map((r,i)=>{const x=L+i*step+(step-bw)/2,y=sy(r.value);return <g key={`${r.label}-${i}`}><rect x={x} y={y} width={bw} height={H-B-y} rx="2" fill="currentColor" className="text-accent-purple"/><text x={x+bw/2} y={H-B+14} textAnchor="middle" fontSize="8" fill="currentColor" className="text-text-muted">{r.label.length>13?`${r.label.slice(0,11)}…`:r.label}</text></g>})}
      <text x="12" y={H/2} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-secondary" transform={`rotate(-90 12 ${H/2})`}>{yLabel}</text>
    </svg>
  </div>;
}

function HeatMap({ title, subtitle, rows }: { title: string; subtitle: string; rows: HeatRow[] }) {
  if (!rows.length || !rows.some(r=>r.values.length)) return null;
  const cols=Array.from(new Set(rows.flatMap(r=>r.values.map(v=>v.key)))); if(!cols.length) return null;
  const W=720, L=115, T=44, cw=Math.max(42,(W-L-12)/cols.length), ch=38, H=T+rows.length*ch+28;
  const vals=rows.flatMap(r=>r.values.map(v=>v.value)).filter(Number.isFinite); if(!vals.length) return null;
  const min=Math.min(...vals), max=Math.max(...vals), span=Math.max(max-min,1e-12);
  return <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
    <div className="mb-3 flex items-start gap-2"><GridFour className="mt-0.5 h-4 w-4 shrink-0 text-accent-cyan"/><div><p className="text-sm font-semibold text-text-primary">{title}</p><p className="text-[11px] leading-4 text-text-muted">{subtitle}</p></div></div>
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={title}>
      {cols.map((c,i)=><text key={c} x={L+i*cw+cw/2} y={24} textAnchor="middle" fontSize="9" fill="currentColor" className="text-text-muted">{c}</text>)}
      {rows.map((r,ri)=><g key={r.label}><text x={L-8} y={T+ri*ch+ch/2+3} textAnchor="end" fontSize="9" fill="currentColor" className="text-text-secondary">{r.label}</text>{cols.map((c,ci)=>{const cell=r.values.find(v=>v.key===c); if(!cell)return null; const opacity=0.12+0.78*((cell.value-min)/span); return <g key={c}><rect x={L+ci*cw+2} y={T+ri*ch+2} width={cw-4} height={ch-4} rx="3" fill="currentColor" className="text-accent-cyan" opacity={opacity}/><text x={L+ci*cw+cw/2} y={T+ri*ch+ch/2+3} textAnchor="middle" fontSize="9" fill="currentColor" className="text-text-primary">{fmt(cell.value)}</text></g>})}</g>)}
    </svg>
  </div>;
}

function transitions(variants: Variant[]) {
  const purines=new Set(['AG','GA']), pyrimidines=new Set(['CT','TC']);
  let ti=0,tv=0,snp=0,indel=0;
  for(const v of variants){ if(v.ref.length===1&&v.alt.length===1){snp++; const pair=`${v.ref.toUpperCase()}${v.alt.toUpperCase()}`; if(purines.has(pair)||pyrimidines.has(pair))ti++; else tv++;} else indel++; }
  return {ti,tv,snp,indel};
}
function densityRows(variants: Variant[]): BarRow[] {
  const bins=new Map<string,number>();
  for(const v of variants){ const mb=Math.floor((v.pos-1)/1_000_000); const key=`${v.chrom}:${mb}-${mb+1}Mb`; bins.set(key,(bins.get(key)??0)+1); }
  return [...bins.entries()].sort((a,b)=>b[1]-a[1]).slice(0,24).map(([label,value])=>({label,value}));
}
function qualityRows(variants: Variant[]): BarRow[] {
  const values:number[] = variants.flatMap(v => { const q=v.qual ?? v.genotype_quality; return typeof q==='number'&&Number.isFinite(q)?[q]:[]; });
  if(values.length<2)return [];
  const min=Math.min(...values), max=Math.max(...values); if(max-min<=1e-12)return [];
  const bins=10, width=(max-min)/bins, counts=Array.from({length:bins},()=>0);
  for(const v of values){const i=Math.min(bins-1,Math.floor((v-min)/width));counts[i]++;}
  return counts.map((value,i)=>({label:`${fmt(min+i*width)}–${fmt(min+(i+1)*width)}`,value}));
}
function sampleQcHeat(stages:Ngs2Stage[]):HeatRow[]{
  const multi=stageData(stages,'multiqc'); if(!multi||!isObj(multi.cross_sample_table))return[];
  const table=multi.cross_sample_table as Obj, rows=isObj(table.rows)?table.rows:null; if(!rows)return[];
  return Object.entries(rows).flatMap(([sample,val])=>{
    if(!isObj(val))return[];
    const values=numericEntries(val);
    return values.length?[{label:sample,values}]:[];
  });
}
function coverageHeat(stages:Ngs2Stage[]):HeatRow[]{
  const cov=stageData(stages,'coverage'); if(!cov)return[];
  const out:HeatRow[]=[];
  const add=(label:string,v:unknown)=>{
    if(!isObj(v))return;
    const values=([1,10,20,30,50] as const).flatMap(x=>{const parsed=n(v[`coverage_${x}x`]);return parsed===null?[]:[{key:`≥${x}x`,value:parsed}];});
    if(values.length)out.push({label,values});
  };
  add('Genome',cov.genome); add('Target',cov.target); return out;
}
function rnaExpressionHeat(stages:Ngs2Stage[]):HeatRow[]{
  const candidates=['differential_expression','rna_expression','expression','quantification'];
  for(const step of candidates){
    const d=stageData(stages,step); if(!d)continue;
    const matrix=d.expression_matrix??d.count_matrix??d.matrix; if(!isObj(matrix))continue;
    const rows=Object.entries(matrix).slice(0,40).flatMap(([gene,val])=>{if(!isObj(val))return[];const values=numericEntries(val);return values.length?[{label:gene,values}]:[];});
    if(rows.length)return rows;
  }
  return [];
}
function rnaPca(stages:Ngs2Stage[]):Point[]{
  for(const step of ['pca','rna_pca','differential_expression']){
    const d=stageData(stages,step);const arr=d&&(d.pca??d.samples);
    if(Array.isArray(arr)){
      const pts:Point[]=arr.filter(isObj).flatMap(r=>{const x=n(r.pc1),y=n(r.pc2);return x===null||y===null?[]:[{x,y}];});
      if(pts.length>1)return pts;
    }
  }
  return[];
}
function rnaVolcano(stages:Ngs2Stage[]):Point[]{
  const d=stageData(stages,'differential_expression');const arr=d&&(d.results??d.genes??d.differential_expression);if(!Array.isArray(arr))return[];
  return arr.filter(isObj).flatMap(r=>{const x=n(r.log2FoldChange)??n(r.log2fc)??n(r.logFC);const p=n(r.padj)??n(r.adjusted_p_value)??n(r.pvalue)??n(r.p_value);return x!==null&&p!==null&&p>0?[{x,y:-Math.log10(p)}]:[];});
}
function rnaMa(stages:Ngs2Stage[]):Point[]{
  const d=stageData(stages,'differential_expression');const arr=d&&(d.results??d.genes??d.differential_expression);if(!Array.isArray(arr))return[];
  return arr.filter(isObj).flatMap(r=>{const mean=n(r.baseMean)??n(r.mean_expression)??n(r.mean);const fc=n(r.log2FoldChange)??n(r.log2fc)??n(r.logFC);return mean!==null&&mean>0&&fc!==null?[{x:Math.log10(mean),y:fc}]:[];});
}

export default function NgsAdvancedPlots({ stages=[] }:{ stages?:Ngs2Stage[] }) {
  if(!Array.isArray(stages)||!stages.length)return null;
  const variants=getVariants(stages);
  const afDepth:Point[]=variants.flatMap(v=>typeof v.dp==='number'&&typeof v.af==='number'&&Number.isFinite(v.dp)&&Number.isFinite(v.af)?[{x:v.dp,y:v.af}]:[]);
  const tv=transitions(variants), qRows=qualityRows(variants), dRows=densityRows(variants), covHeat=coverageHeat(stages), qcHeat=sampleQcHeat(stages);
  const exprHeat=rnaExpressionHeat(stages), pca=rnaPca(stages), volcano=rnaVolcano(stages), ma=rnaMa(stages);
  const hasAny=variants.length>0||covHeat.length>0||qcHeat.length>0||exprHeat.length>0||pca.length>1||volcano.length>1||ma.length>1;
  if(!hasAny)return null;
  return <section className="space-y-4 rounded-xl border border-glass-border bg-surface-0 p-4" aria-label="Advanced NGS plots">
    <div><h3 className="text-sm font-semibold text-text-primary">Advanced NGS visual analytics</h3><p className="mt-1 text-[11px] leading-4 text-text-muted">Plots are rendered only when the required underlying measurements exist. No missing values are synthesized.</p></div>
    <div className="grid gap-4 xl:grid-cols-2">
      <HeatMap title="Coverage heat map" subtitle="Observed genome/target fractions reaching each depth threshold from the coverage stage." rows={covHeat}/>
      <HeatMap title="Sample QC heat map" subtitle="Cross-sample MultiQC measurements exactly as returned for this cohort." rows={qcHeat}/>
      <Scatter title="Variant allele fraction vs depth" subtitle="Each point is a returned variant with both allele fraction and read depth available." points={afDepth} xLabel="Depth (DP)" yLabel="Allele fraction"/>
      <Bars title="Ti/Tv and variant-type distribution" subtitle="Transition/transversion and SNP/indel counts computed directly from returned REF/ALT alleles." rows={[{label:'Transitions',value:tv.ti},{label:'Transversions',value:tv.tv},{label:'SNPs',value:tv.snp},{label:'Indels',value:tv.indel}]} yLabel="Variant count"/>
      <Bars title="Chromosome-wise variant density" subtitle="Variant counts in 1 Mb genomic bins derived from returned chromosome and position fields." rows={dRows} yLabel="Variants / 1 Mb bin"/>
      <Bars title="Variant quality distribution" subtitle="Shown only when returned variants contain QUAL or genotype-quality values." rows={qRows} yLabel="Variant count"/>
      <HeatMap title="RNA-seq expression heat map" subtitle="Rendered only from a returned gene-by-sample expression/count matrix; unavailable in FASTQ-only preview mode." rows={exprHeat}/>
      <Scatter title="RNA-seq PCA" subtitle="Rendered only when production RNA-seq output contains PC1 and PC2 coordinates." points={pca} xLabel="PC1" yLabel="PC2"/>
      <Scatter title="RNA-seq volcano plot" subtitle="Rendered only from returned log2 fold-change and p-value/adjusted-p-value statistics." points={volcano} xLabel="log2 fold change" yLabel="−log10(p)"/>
      <Scatter title="RNA-seq MA plot" subtitle="Rendered only when returned differential-expression output contains mean expression and log2 fold change." points={ma} xLabel="log10 mean expression" yLabel="log2 fold change"/>
    </div>
  </section>;
}
