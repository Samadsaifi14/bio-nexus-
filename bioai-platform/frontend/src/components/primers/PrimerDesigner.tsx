"use client";
import { useState, useRef, useEffect } from "react";
import { LoaderCircle, Download } from "lucide-react";
import { downloadTsv } from "@/lib/export-utils";
import { useAuditTrail } from "@/hooks/useAuditTrail";

type PrimerPair = {
  pair_index: number;
  left_seq: string;  left_tm: number;  left_gc: number;  left_pos: number;  left_len: number;
  right_seq: string; right_tm: number; right_gc: number; right_pos: number; right_len: number;
  product_size: number; penalty: number;
};

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
  const auditedRef = useRef(false);

  useEffect(() => {
    const stored = sessionStorage.getItem('primer_sequence');
    if (stored) {
      sessionStorage.removeItem('primer_sequence');
      setSequence(stored);
    }
  }, []);

  async function design() {
    setError(null); setPairs([]); setLoading(true);
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
        <span className="bg-purple-500/20 text-purple-300 font-bold">{seq.slice(rStart, pair.right_pos + 1)}</span>
        <span className="text-text-muted">{seq.slice(pair.right_pos + 1)}</span>
      </>
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-text-primary font-semibold mb-3">Primer Design (Primer3)</h3>
        <p className="text-text-muted text-xs mb-4">Input a DNA/CDS sequence. Primer3 runs locally &mdash; instant results, no rate limits.</p>

        <textarea value={sequence} onChange={e => setSequence(e.target.value)} rows={5}
          placeholder="ATGCGTACGTAGCTGATCGATCGATCG..."
          className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition font-mono text-xs resize-none bg-surface-1 text-text-primary" />

        <div className="grid grid-cols-3 gap-3 mt-3">
          {[
            { label: "Min product (bp)", value: productMin, set: setProductMin, min: 50, max: 999 },
            { label: "Max product (bp)", value: productMax, set: setProductMax, min: 100, max: 2000 },
            { label: "Optimal Tm (&deg;C)", value: optTm, set: setOptTm, min: 50, max: 75 },
          ].map(({ label, value, set, min, max }) => (
            <div key={label}>
              <label className="text-xs text-text-muted block mb-1">{label}</label>
              <input type="number" value={value} min={min} max={max}
                onChange={e => set(+e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-glass-border bg-surface-1 text-sm text-text-primary focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition" />
            </div>
          ))}
        </div>

        {error && <p className="mt-2 text-error text-sm">{error}</p>}

        <button onClick={design} disabled={loading || !sequence.trim()}
          className="mt-4 w-full btn-primary py-2.5 text-sm flex items-center justify-center gap-2 disabled:opacity-40">
          {loading ? <><LoaderCircle className="w-4 h-4 animate-spin" /> Designing&hellip;</> : "Design Primers"}
        </button>
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

          {selectedPair !== null && (() => {
            const p = pairs[selectedPair];
            return (
              <div className="space-y-3">
                {[
                  { label: "Forward (5'&rarr;3')", seq: p.left_seq, tm: p.left_tm, gc: p.left_gc, pos: p.left_pos, color: "var(--accent-cyan)" },
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
                    <span className="flex items-center gap-1"><span className="w-3 h-2 bg-purple-500/30 rounded inline-block" />Reverse</span>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
