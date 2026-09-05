'use client';

import { useState, useCallback, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Brain, CircleNotch as Loader2, WarningCircle as AlertTriangle, CheckCircle, Info, ShieldCheck, CaretDown, CaretRight } from '@phosphor-icons/react';
import { fadeUp, fadeIn } from '@/lib/animations';
import { interpretToolResult, type AIInterpretation } from '@/lib/api';
import { getExperimentEvidence, getClaimEvidence, type EvidenceGraph, type EvidenceClaimTrace } from '@/lib/scientific-api';

interface AIResultSummaryProps {
  toolName: string;
  result: Record<string, unknown>;
  title?: string;
  compact?: boolean;
  jobId?: string;
}

type NumericToken = { text: string; value: number };
const SUPERS: Record<string, string> = { '⁰':'0','¹':'1','²':'2','³':'3','⁴':'4','⁵':'5','⁶':'6','⁷':'7','⁸':'8','⁹':'9','⁻':'-','⁺':'+' };

function normalizeText(value: string) {
  return value.replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]/g, ch => SUPERS[ch]).replace(/(\d)\s*,\s*(\d)/g, '$1$2').replace(/(\d+(?:\.\d+)?)\s*[×✕*]\s*10\s*\^?\s*(-?\d+)/g, '$1e$2');
}
function numericTokens(value: string): NumericToken[] { return (normalizeText(value).match(/-?\d+(?:\.\d+)?(?:e[+-]?\d+)?%?/gi) ?? []).map(text => ({ text, value: Math.abs(parseFloat(text.replace(/%$/, ''))) })); }
function nearlyEqual(a:number,b:number){ return Math.abs(a-b) <= 0.001*Math.max(Math.abs(a),Math.abs(b),1); }
function isGrounded(value:number, sourceValues:NumericToken[]){ if(Number.isInteger(value)&&value>=0&&value<=5)return true; return sourceValues.some(s=>nearlyEqual(s.value,value)||nearlyEqual(s.value,value/100)||nearlyEqual(s.value,value*100)); }
function checkNumericGrounding(interpretation:AIInterpretation,result:Record<string,unknown>){ const source=numericTokens(JSON.stringify(result)); const generated=[interpretation.headline,interpretation.summary,...interpretation.findings,...interpretation.caveats].join(' '); const ungrounded=numericTokens(generated).filter(t=>!isGrounded(t.value,source)).map(t=>t.text); return {grounded:ungrounded.length===0,ungrounded:[...new Set(ungrounded)].slice(0,5)}; }

function TracePanel({ trace }: { trace: EvidenceClaimTrace }) {
  const ordered = trace.reviewer_path.flatMap(type => (trace.by_type[type] ?? []).map(node => ({ type, node })));
  return <div className="mt-2 rounded-xl border border-glass-border bg-surface-1 p-3">
    <div className="mb-2 flex items-center justify-between gap-2"><span className="text-[10px] font-medium uppercase tracking-wide text-text-muted">Evidence trace</span><span className="text-[10px] text-text-muted">{trace.complete_path ? 'provenance path complete' : 'provenance gaps present'}</span></div>
    <div className="space-y-1.5">{ordered.map(({type,node}) => <div key={node.id} className="grid grid-cols-[92px_1fr] gap-2 text-xs"><span className="font-medium capitalize text-text-muted">{type}</span><span className="break-words text-text-secondary">{node.label || 'not recorded'}</span></div>)}</div>
    <p className="mt-2 text-[10px] leading-relaxed text-text-muted">{trace.interpretation}</p>
  </div>;
}

export function AIResultSummary({ toolName, result, title='AI Evidence Engine', compact=false, jobId }: AIResultSummaryProps) {
  const [interpretation,setInterpretation]=useState<AIInterpretation|null>(null); const [loading,setLoading]=useState(false); const [error,setError]=useState<string|null>(null); const [warning,setWarning]=useState<string|null>(null);
  const [graph,setGraph]=useState<EvidenceGraph|null>(null); const [graphError,setGraphError]=useState<string|null>(null); const [openClaim,setOpenClaim]=useState<string|null>(null); const [traces,setTraces]=useState<Record<string,EvidenceClaimTrace>>({});
  const resolvedJobId = jobId || (typeof result.job_id === 'string' ? result.job_id : (typeof result.experiment_id === 'string' ? result.experiment_id : undefined));

  useEffect(()=>{ let active=true; if(!resolvedJobId){setGraph(null);return;} getExperimentEvidence(resolvedJobId).then(g=>{if(active){setGraph(g);setGraphError(null);}}).catch(err=>{if(active)setGraphError(err instanceof Error?err.message:'Evidence graph unavailable.');}); return()=>{active=false;}; },[resolvedJobId]);

  const toggleClaim = useCallback(async (claimId:string)=>{ if(openClaim===claimId){setOpenClaim(null);return;} setOpenClaim(claimId); if(!resolvedJobId||traces[claimId])return; try{const trace=await getClaimEvidence(resolvedJobId,claimId); setTraces(prev=>({...prev,[claimId]:trace}));}catch(err){setGraphError(err instanceof Error?err.message:'Claim evidence unavailable.');} },[openClaim,resolvedJobId,traces]);

  const handleInterpret=useCallback(async()=>{ if(loading)return; setLoading(true);setError(null);setWarning(null);setInterpretation(null); try{ const data=await interpretToolResult(toolName,result); if(!data?.summary?.trim()){setError('AI explanation was empty and has been withheld.');return;} const {grounded,ungrounded}=checkNumericGrounding(data,result); setInterpretation(data); if(!grounded)setWarning(`Caution — value(s) ${ungrounded.join(', ')} in this explanation could not be traced to the raw result. Review the deterministic values above first.`); }catch(err:unknown){setError(err instanceof Error?err.message:'AI explanation is unavailable. Use the deterministic result and provenance shown above.');}finally{setLoading(false);} },[toolName,result,loading]);

  return <motion.div variants={fadeUp} className="rounded-2xl border border-glass-border bg-surface-0 p-5">
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2"><Brain className="h-5 w-5 text-accent-cyan"/><div><h3 className="font-semibold text-text-primary">{title}</h3><p className="mt-0.5 flex items-center gap-1 text-[10px] text-text-muted"><ShieldCheck className="h-3 w-3"/>Numeric claims are checked against the emitted result; persisted experiment claims can expose their evidence chain.</p></div></div>{!interpretation&&!loading&&<motion.button variants={fadeIn} onClick={handleInterpret} className="rounded-lg border border-accent-cyan/25 bg-accent-cyan/8 px-4 py-2 text-sm font-medium text-accent-cyan transition hover:bg-accent-cyan/12" disabled={loading}>Explain result</motion.button>}</div>
    {error&&!loading&&<div className="mb-2 rounded-xl border border-warn/25 bg-warn/7 p-4"><p className="flex items-start gap-2 text-sm text-text-secondary"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn"/>{error}</p></div>}
    {loading&&<div className="flex items-center gap-2 py-2 text-sm text-text-muted"><Loader2 className="h-4 w-4 animate-spin"/>Generating an evidence-constrained explanation...</div>}
    {interpretation&&!loading&&<motion.div variants={fadeIn} className="space-y-4">{warning&&<div className="rounded-xl border border-warn/25 bg-warn/7 p-4"><p className="flex items-start gap-2 text-sm text-text-secondary"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn"/>{warning}</p></div>}<p className={`${compact?'text-base':'text-lg'} font-semibold text-text-primary`}>{interpretation.headline}</p><p className={`${compact?'text-sm':'text-base'} leading-relaxed text-text-secondary`}>{interpretation.summary}</p>{interpretation.findings.length>0&&<div><p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">Evidence-backed observations</p><ul className="space-y-1.5">{interpretation.findings.map((f,i)=><li key={`${f}-${i}`} className="flex items-start gap-2 text-sm text-text-secondary"><CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-good"/>{f}</li>)}</ul></div>}{interpretation.caveats.length>0&&<div><p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">Limitations</p><ul className="space-y-1.5">{interpretation.caveats.map((c,i)=><li key={`${c}-${i}`} className="flex items-start gap-2 text-sm text-text-secondary"><Info className="mt-0.5 h-4 w-4 shrink-0 text-warn"/>{c}</li>)}</ul></div>}<div className="border-t border-glass-border pt-2"><button onClick={()=>{setInterpretation(null);setError(null);setWarning(null);}} className="text-xs text-text-muted transition hover:text-text-primary">Clear explanation</button></div></motion.div>}
    {graph&&graph.claims.length>0&&<div className="mt-4 border-t border-glass-border pt-4"><div className="mb-2"><p className="text-xs font-medium uppercase tracking-wide text-text-muted">Audited claim traces</p><p className="mt-1 text-[10px] text-text-muted">Click a persisted sentence to inspect Claim → Evidence → Algorithm → Database → Version → Parameters → Confidence → Benchmark.</p></div><div className="space-y-2">{graph.claims.map((claim,i)=>{const id=String(claim.id??`claim-${i+1}`);const text=String(claim.text??'Claim text unavailable');const rejected=Boolean(claim.rejected);return <div key={id}><button type="button" onClick={()=>toggleClaim(id)} className="flex w-full items-start gap-2 rounded-xl border border-glass-border bg-surface-1 p-3 text-left transition hover:border-accent-cyan/30"><span className="mt-0.5 text-text-muted">{openClaim===id?<CaretDown className="h-4 w-4"/>:<CaretRight className="h-4 w-4"/>}</span><span className="flex-1 text-sm text-text-secondary">{text}</span><span className={`text-[10px] ${rejected?'text-warn':'text-good'}`}>{rejected?'rejected':'admitted'}</span></button>{openClaim===id&&traces[id]&&<TracePanel trace={traces[id]}/>}</div>;})}</div></div>}
    {graphError&&resolvedJobId&&<p className="mt-3 text-[10px] text-text-muted">Evidence trace unavailable: {graphError}</p>}
  </motion.div>;
}
