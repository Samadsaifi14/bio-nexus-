"use client";
import { useState, useRef, useEffect } from "react";
import { CircleNotch as LoaderCircle, Download, MagnifyingGlass as Search, Dna, ArrowRight, Flask as Beaker } from '@phosphor-icons/react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, Cell } from "recharts";
import { downloadTsv } from "@/lib/export-utils";
import { useAuditTrail } from "@/hooks/useAuditTrail";
import { CriticalButton, FlatInput, FlatTextarea } from "@/components/ui";
import { searchPrimerTargets, analyzePrimer, fetchSequence } from "@/lib/api";
import { extractErrorMessage } from "@/lib/errors";
import type { PrimerSearchHit, PrimerAnalyzeResponse, PrimerStructure } from "@/lib/api";

type PrimerPair = {
  pair_index: number;
  left_seq: string;  left_tm: number;  left_gc: number;  left_pos: number;  left_len: number;
  right_seq: string; right_tm: number; right_gc: number; right_pos: number; right_len: number;
  product_size: number; penalty: number;
};

const RISK_TONES: Record<string, string> = {
  high: "text-error bg-error/10 border-error/30",
  medium: "text-accent-amber bg-accent-amber/10 border-accent-amber/30",
  low: "text-accent-cyan bg-accent-cyan/10 border-accent-cyan/30",
  none: "text-molecule-protein bg-molecule-protein/10 border-molecule-protein/30",
};

function RiskBadge({ structure }: { structure: PrimerStructure }) {
  const cls = RISK_TONES[structure.risk] ?? RISK_TONES.none;
  const label = structure.risk.charAt(0).toUpperCase() + structure.risk.slice(1);
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}>{label}</span>;
}

function RiskCard({ title, structure }: { title: string; structure: PrimerStructure }) {
  return (
    <div className="bg-surface-0 rounded-xl p-3 border border-glass-border">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-text-muted">{title}</span>
        <RiskBadge structure={structure} />
      </div>
      {structure.stem_length > 0 ? (
        <>
          <p className="text-xs text-text-secondary">
            &Delta;G <span className="text-text-primary font-mono">{structure.dg.toFixed(1)}</span> kcal/mol
            &middot; stem <span className="text-text-primary font-mono">{structure.stem_length}</span> bp
          </p>
          <p className="text-xs font-mono text-text-secondary mt-1 break-all">{structure.stem}</p>
          {"loop" in structure && structure.loop && (
            <p className="text-xs text-text-muted mt-0.5">loop: <span className="font-mono">{structure.loop}</span></p>
          )}
          {(structure.involves_a3 || structure.involves_b3) && (
            <p className="text-xs text-error mt-1">3&#39; end involved &mdash; extension-competent</p>
          )}
        </>
      ) : (
        <p className="text-xs text-text-muted">No significant structure predicted.</p>
      )}
    </div>
  );
}

export function PrimerDesigner() {
  const audit = useAuditTrail();
  const [sequence, setSequence] = useState("");
  const [productMin, setProductMin] = useState(100);
  const [productMax, setProductMax] = useState(500);
  const [optTm, setOptTm] = useState(60);
  const [pairs, setPairs] = useState<PrimerPair[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPair, setSelectedPair] = useState<number | null>(null);

  // NCBI gene/sequence search + retrieval
  const [geneQuery, setGeneQuery] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchResults, setSearchResults] = useState<PrimerSearchHit[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [usingSeq, setUsingSeq] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Selected-pair QC
  const [analysis, setAnalysis] = useState<PrimerAnalyzeResponse | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const auditedRef = useRef(false);

  useEffect(() => {
    const stored = sessionStorage.getItem('primer_sequence');
    if (stored) {
      sessionStorage.removeItem('primer_sequence');
      setSequence(stored);
    }
  }, []);

  // Auto-run QC (hairpin / dimer / in-silico PCR) for the selected pair.
  useEffect(() => {
    if (pairs.length === 0 || selectedPair === null) return;
    const p = pairs[selectedPair];
    const tmpl = sequence.replace(/\s/g, "").toUpperCase();
    if (!tmpl) return;
    let cancelled = false;
    setAnalyzing(true);
    setAnalysisError(null);
    analyzePrimer({
      left_seq: p.left_seq,
      right_seq: p.right_seq,
      template: tmpl,
      left_pos: p.left_pos,
      right_pos: p.right_pos,
      expected_product: p.product_size,
    })
      .then(res => { if (!cancelled) setAnalysis(res); })
      .catch(e => { if (!cancelled) setAnalysisError(extractErrorMessage(e)); })
      .finally(() => { if (!cancelled) setAnalyzing(false); });
    return () => { cancelled = true; };
  }, [selectedPair, pairs, sequence]);

  async function searchGene() {
    const q = geneQuery.trim();
    if (!q) return;
    setSearchLoading(true); setSearchError(null); setFetchError(null); setSearchResults([]);
    try {
      const res = await searchPrimerTargets(q, 12);
      if (res.error) setSearchError(res.error);
      else setSearchResults(res.results);
    } catch (e: any) {
      setSearchError(extractErrorMessage(e));
    } finally { setSearchLoading(false); }
  }

  async function applySequence(hit: PrimerSearchHit) {
    setUsingSeq(hit.accession); setFetchError(null);
    try {
      const res = await fetchSequence(hit.accession);
      if (res.error) {
        setFetchError(res.error);
      } else {
        setSequence(res.sequence);
        audit.emitSuccess('primer_ncbi_retrieval', 'NCBI', hit.accession, `${res.length}bp`);
      }
    } catch (e: any) {
      setFetchError(extractErrorMessage(e));
    } finally { setUsingSeq(null); }
  }

  async function design() {
    setError(null); setPairs([]); setSelectedPair(null); setAnalysis(null); setLoading(true);
    auditedRef.current = false;
    try {
      const res = await fetch("/api/backend/api/primers/design", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sequence, product_size_min: productMin, product_size_max: productMax, opt_tm: optTm }),
      });
      if (!res.ok) {
        const d = await res.json();
        const msg = Array.isArray(d.detail)
          ? d.detail.map((e: any) => e.msg || String(e)).join("; ")
          : typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
        throw new Error(msg || res.statusText);
      }
      const result = await res.json();
      setPairs(result);
      setSelectedPair(0);
      if (!auditedRef.current) { auditedRef.current = true; audit.emitSuccess('primer_design', 'Primer3', `${sequence.length}bp`, `${result.length} pairs`); }
    } catch (e: any) { setError(e.message); audit.emitFailed('primer_design', 'Primer3', `${sequence.length}bp`, e.message); }
    finally { setLoading(false); }
  }

  function copyPair(p: PrimerPair) {
    navigator.clipboard.writeText(`Forward: ${p.left_seq}\nReverse: ${p.right_seq}`);
  }

  const highlightSequence = (seq: string, pair: PrimerPair | null) => {
    if (!pair) return seq;
    const lEnd = pair.left_pos + pair.left_len;
    const rStart = pair.right_pos - pair.right_len + 1;
    return (
      <>
        <span className="text-text-muted">{seq.slice(0, pair.left_pos)}</span>
        <span className="bg-accent-cyan/20 text-accent-cyan font-bold">{seq.slice(pair.left_pos, lEnd)}</span>
        <span className="text-text-muted">{seq.slice(lEnd, rStart)}</span>
        <span className="bg-accent-purple/20 text-accent-purple font-bold">{seq.slice(rStart, pair.right_pos + 1)}</span>
        <span className="text-text-muted">{seq.slice(pair.right_pos + 1)}</span>
      </>
    );
  };

  const selected = selectedPair !== null && pairs[selectedPair] ? pairs[selectedPair] : null;
  const tmData = pairs.map(p => ({ name: `P${p.pair_index + 1}`, Left: +p.left_tm.toFixed(1), Right: +p.right_tm.toFixed(1) }));
  const gcData = pairs.map(p => ({ name: `P${p.pair_index + 1}`, Left: +p.left_gc.toFixed(1), Right: +p.right_gc.toFixed(1) }));
  const productData = pairs.map(p => ({ name: `P${p.pair_index + 1}`, Size: p.product_size }));

  const chartTooltip = { contentStyle: { background: "var(--chart-tooltip-bg)", border: "1px solid var(--chart-tooltip-border)", borderRadius: 8, fontSize: 12 }, labelStyle: { color: "var(--chart-tooltip-label)" }, itemStyle: { color: "var(--chart-tooltip-item)" } };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-text-primary font-semibold mb-3">Primer Design (Primer3)</h3>
        <p className="text-text-muted text-xs mb-4">Search NCBI for a gene, retrieve its mRNA/CDS, then design and QC primers locally &mdash; instant results, no rate limits.</p>

        {/* NCBI gene search */}
        <div className="bg-surface-0 rounded-xl border border-glass-border p-3 mb-3">
          <div className="flex items-center gap-2 mb-2">
            <Dna className="w-4 h-4 text-accent-cyan" />
            <span className="text-xs font-semibold text-text-secondary">1 &middot; Find a gene on NCBI</span>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={geneQuery}
              onChange={e => { setGeneQuery(e.target.value); setSearchError(null); }}
              onKeyDown={e => e.key === 'Enter' && searchGene()}
              placeholder="e.g. TP53 human, BRCA1 human, HBB mRNA"
              className="flex-1 px-3 py-2 rounded-lg border border-glass-border focus:border-accent-cyan focus:ring-2 focus:ring-accent-cyan/20 outline-none transition text-xs bg-surface-0 text-text-primary"
            />
            <button onClick={searchGene} disabled={searchLoading || !geneQuery.trim()}
              className="px-3 py-2 bg-accent-cyan text-void text-xs font-medium rounded-lg hover:bg-accent-hover transition disabled:opacity-50 flex items-center gap-1.5">
              {searchLoading ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
              Search NCBI
            </button>
          </div>
          {searchError && <p className="mt-2 text-xs text-error">{searchError}</p>}
          {fetchError && <p className="mt-2 text-xs text-error">{fetchError}</p>}

          {searchResults.length > 0 && (
            <div className="mt-3 max-h-56 overflow-y-auto space-y-1.5">
              {searchResults.map((r, i) => (
                <div key={i} className="flex items-center gap-2 p-2 rounded-lg border border-glass-border hover:border-accent-cyan/30 transition">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <code className="text-xs font-mono text-accent-cyan">{r.accession}</code>
                      <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${
                        r.record_type === 'mRNA' ? 'text-molecule-rna bg-molecule-rna/10' : 'text-text-muted bg-surface-0'
                      }`}>{r.record_type}</span>
                      {r.suggested_use === 'ideal' && (
                        <span className="px-1.5 py-0.5 rounded-full text-[10px] font-medium text-molecule-protein bg-molecule-protein/10">ideal template</span>
                      )}
                    </div>
                    <p className="text-xs text-text-secondary truncate mt-0.5">{r.title}</p>
                    <p className="text-[10px] text-text-muted">{r.organism} &middot; {r.length.toLocaleString()} bp</p>
                  </div>
                  <button onClick={() => applySequence(r)}
                    disabled={usingSeq === r.accession}
                    className="shrink-0 px-2.5 py-1.5 rounded-lg text-xs font-medium border border-accent-cyan/40 text-accent-cyan hover:bg-accent-cyan/10 transition disabled:opacity-50 flex items-center gap-1">
                    {usingSeq === r.accession ? <LoaderCircle className="w-3 h-3 animate-spin" /> : <ArrowRight className="w-3 h-3" />}
                    Use sequence
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Sequence input */}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-semibold text-text-secondary">2 &middot; DNA / CDS sequence</span>
          {sequence && <span className="text-[10px] text-text-muted">{sequence.replace(/\s/g, "").length.toLocaleString()} bp</span>}
        </div>
        <FlatTextarea value={sequence} onChange={e => setSequence(e.target.value)} rows={5}
          placeholder="Paste a DNA/CDS sequence, or use 'Use sequence' above to fetch one from NCBI..." className="w-full text-xs" />

        <div className="grid grid-cols-3 gap-3 mt-3">
          {[
            { label: "Min product (bp)", value: productMin, set: setProductMin, min: 50, max: 999 },
            { label: "Max product (bp)", value: productMax, set: setProductMax, min: 100, max: 2000 },
            { label: "Optimal Tm (&deg;C)", value: optTm, set: setOptTm, min: 50, max: 75 },
          ].map(({ label, value, set, min, max }) => (
            <div key={label}>
              <label className="text-xs text-text-muted block mb-1">{label}</label>
              <FlatInput type="number" value={value} min={min} max={max}
                onChange={e => set(+e.target.value)} />
            </div>
          ))}
        </div>

        {error && <p className="mt-2 text-error text-sm">{error}</p>}

        <CriticalButton onClick={design} disabled={loading || !sequence.trim()} className="mt-4 w-full">
          {loading ? <><LoaderCircle className="w-4 h-4 animate-spin" /> Designing&hellip;</> : "Design Primers"}
        </CriticalButton>
      </div>

      {pairs.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex gap-2 flex-wrap">
              {pairs.map(p => (
                <button key={p.pair_index} onClick={() => setSelectedPair(p.pair_index)}
                  className={`px-3 py-1 rounded-full text-xs border transition ${
                    selectedPair === p.pair_index
                      ? "border-accent-cyan bg-accent-cyan/10 text-accent-cyan"
                      : "border-glass-border text-text-muted hover:border-white/20"
                  }`}>
                  Pair {p.pair_index + 1} &middot; {p.product_size}bp
                </button>
              ))}
            </div>
            <button onClick={() => {
              const fasta = pairs.flatMap(p => [
                `>pair${p.pair_index + 1}_forward Tm=${p.left_tm.toFixed(1)} GC=${p.left_gc.toFixed(1)}% pos=${p.left_pos} len=${p.left_len}`,
                p.left_seq,
                `>pair${p.pair_index + 1}_reverse Tm=${p.right_tm.toFixed(1)} GC=${p.right_gc.toFixed(1)}% pos=${p.right_pos} len=${p.right_len}`,
                p.right_seq,
              ]).join('\n');
              const a = document.createElement('a');
              a.download = 'primers.fasta';
              a.href = 'data:text/fasta;charset=utf-8,' + encodeURIComponent(fasta);
              a.click();
            }} className="btn-ghost text-xs px-2 py-1 flex items-center gap-1">
              <Download className="w-3 h-3" /> FASTA
            </button>
            <button onClick={() => downloadTsv(
              ["Pair", "Forward seq", "Fwd Tm", "Fwd GC%", "Fwd Pos", "Fwd Len", "Reverse seq", "Rev Tm", "Rev GC%", "Rev Pos", "Rev Len", "Product size", "Penalty"],
              pairs.map(p => [String(p.pair_index + 1), p.left_seq, p.left_tm.toFixed(1), p.left_gc.toFixed(1), String(p.left_pos), String(p.left_len), p.right_seq, p.right_tm.toFixed(1), p.right_gc.toFixed(1), String(p.right_pos), String(p.right_len), String(p.product_size), p.penalty.toFixed(3)]),
              "primers.tsv"
            )} className="btn-ghost text-xs px-2 py-1 flex items-center gap-1">
              <Download className="w-3 h-3" /> Export TSV
            </button>
          </div>

          {/* All-pairs overview charts */}
          <div className="bg-surface-1 rounded-xl p-4 border border-glass-border">
            <p className="text-xs text-text-muted mb-3">All candidate pairs &mdash; Tm, GC and product size</p>
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-surface-0 rounded-lg p-2">
                <p className="text-[10px] text-text-muted mb-1">Melting temperature (&deg;C)</p>
                <ResponsiveContainer width="100%" height={120}>
                  <BarChart data={tmData} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#64748B" }} />
                    <YAxis domain={[40, 75]} tick={{ fontSize: 9, fill: "#64748B" }} />
                    <Tooltip {...chartTooltip} />
                    <Legend wrapperStyle={{ fontSize: 9 }} />
                    <Bar dataKey="Left" fill="#22D3EE" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="Right" fill="#A855F7" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="bg-surface-0 rounded-lg p-2">
                <p className="text-[10px] text-text-muted mb-1">GC content (%)</p>
                <ResponsiveContainer width="100%" height={120}>
                  <BarChart data={gcData} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#64748B" }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: "#64748B" }} />
                    <Tooltip {...chartTooltip} />
                    <Legend wrapperStyle={{ fontSize: 9 }} />
                    <Bar dataKey="Left" fill="#22D3EE" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="Right" fill="#A855F7" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="bg-surface-0 rounded-lg p-2">
                <p className="text-[10px] text-text-muted mb-1">Product size (bp)</p>
                <ResponsiveContainer width="100%" height={120}>
                  <BarChart data={productData} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#64748B" }} />
                    <YAxis tick={{ fontSize: 9, fill: "#64748B" }} />
                    <Tooltip {...chartTooltip} />
                    <Bar dataKey="Size" fill="#F59E0B" radius={[3, 3, 0, 0]}>
                      {productData.map((d, i) => <Cell key={i} fill={i === selectedPair ? "#22D3EE" : "#F59E0B"} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {selected && (() => {
            const p = selected;
            return (
              <div className="space-y-3">
                {[
                  { label: "Forward (5'&rarr;3')", seq: p.left_seq, tm: p.left_tm, gc: p.left_gc, pos: p.left_pos, color: "rgb(var(--accent-cyan))" },
                  { label: "Reverse (5'&rarr;3')", seq: p.right_seq, tm: p.right_tm, gc: p.right_gc, pos: p.right_pos, color: "#A855F7" },
                ].map(primer => (
                  <div key={primer.label} className="bg-surface-1 rounded-xl p-4 border border-glass-border">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium" style={{ color: primer.color }}>{primer.label}</span>
                      <div className="flex gap-4 text-xs text-text-muted">
                        <span>Tm {primer.tm.toFixed(1)}&deg;C</span>
                        <span>GC {primer.gc.toFixed(1)}%</span>
                        <span>Pos {primer.pos}</span>
                      </div>
                    </div>
                    <code className="text-sm font-mono" style={{ color: primer.color }}>{primer.seq}</code>
                  </div>
                ))}

                <div className="flex items-center justify-between text-sm text-text-muted px-1">
                  <span>Product size: <span className="text-text-secondary">{p.product_size} bp</span></span>
                  <span>Penalty: <span className="text-text-secondary">{p.penalty.toFixed(3)}</span></span>
                  <button onClick={() => copyPair(p)} className="text-accent-cyan hover:text-accent-cyan/80 transition text-xs">
                    Copy sequences
                  </button>
                </div>

                <div className="bg-surface-1 rounded-xl p-3 border border-glass-border">
                  <p className="text-xs text-text-muted mb-2">Binding positions in sequence</p>
                  <div className="font-mono text-xs break-all leading-6">
                    {highlightSequence(sequence.replace(/\s/g, "").toUpperCase(), p)}
                  </div>
                  <div className="flex gap-4 mt-2 text-xs">
                    <span className="flex items-center gap-1"><span className="w-3 h-2 bg-accent-cyan/30 rounded inline-block" />Forward</span>
                    <span className="flex items-center gap-1"><span className="w-3 h-2 bg-accent-purple/30 rounded inline-block" />Reverse</span>
                  </div>
                </div>

                {/* QC panel */}
                <div className="bg-surface-1 rounded-xl p-4 border border-glass-border">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs text-text-muted">Oligo QC + in-silico PCR (reference-verified)</p>
                    {analyzing && <LoaderCircle className="w-4 h-4 animate-spin text-accent-cyan" />}
                  </div>

                  {analysisError && <p className="text-xs text-error mb-2">{analysisError}</p>}

                  {analysis && (
                    <div className="space-y-3">
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                        <RiskCard title="Hairpin (forward)" structure={analysis.qc.left.hairpin} />
                        <RiskCard title="Self-dimer (forward)" structure={analysis.qc.left.self_dimer} />
                        <RiskCard title="Hetero-dimer" structure={analysis.qc.hetero_dimer} />
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <RiskCard title="Hairpin (reverse)" structure={analysis.qc.right.hairpin} />
                        <RiskCard title="Self-dimer (reverse)" structure={analysis.qc.right.self_dimer} />
                      </div>

                      {analysis.pcr && (
                        <div className="bg-surface-0 rounded-xl p-3 border border-glass-border">
                          <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs">
                            <span className="flex items-center gap-1.5">
                              <Beaker className="w-3.5 h-3.5 text-accent-cyan" />
                              Specificity:
                              {analysis.pcr.specific
                                ? <span className="text-molecule-protein font-medium">each primer binds once</span>
                                : <span className="text-error font-medium">multiple sites ({analysis.pcr.forward_binding_sites} fwd / {analysis.pcr.reverse_binding_sites} rev)</span>}
                            </span>
                            <span>Fwd sites <span className="text-text-primary font-mono">{analysis.pcr.forward_binding_sites}</span></span>
                            <span>Rev sites <span className="text-text-primary font-mono">{analysis.pcr.reverse_binding_sites}</span></span>
                            <span>Primer3 match
                              {analysis.pcr.primer3_consistent
                                ? <span className="text-molecule-protein font-medium"> &check;</span>
                                : <span className="text-error font-medium"> mismatch</span>}
                            </span>
                            <span>Amplicon
                              {analysis.pcr.matches_product_size
                                ? <span className="text-molecule-protein font-medium"> {p.product_size} bp &check;</span>
                                : <span className="text-error font-medium"> mismatch</span>}
                            </span>
                          </div>
                          {analysis.pcr.amplicons.length > 0 && (
                            <p className="text-[10px] text-text-muted mt-2">
                              Predicted amplicons: {analysis.pcr.amplicons.slice(0, 3).map(a => `[${a.start}..${a.end}] ${a.length}bp`).join("  ")}
                            </p>
                          )}
                          {analysis.pcr.note && (
                            <p className="text-[10px] text-text-muted mt-1">{analysis.pcr.note}</p>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {!analysis && !analyzing && !analysisError && (
                    <p className="text-xs text-text-muted">Select a pair to run QC checks.</p>
                  )}
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
