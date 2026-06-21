"use client";
import { useState, useRef } from "react";
import { ArrowLeft, GitFork, Upload, FileText, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { PhyloTreeViewer } from "@/components/phylo/PhyloTreeViewer";

export default function PhyloPage() {
  const [mode, setMode] = useState<"align" | "upload">("align");
  const [fasta, setFasta] = useState("");
  const [newickText, setNewickText] = useState("");
  const [newick, setNewick] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleBuildTree() {
    if (!fasta.trim()) { setError("Enter at least 2 sequences in FASTA format."); return; }
    setLoading(true); setError(null);
    try {
      const res = await fetch("/api/backend/api/alignment/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sequence: fasta.trim(), stype: "protein" }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Alignment failed");
      const data = await res.json();
      if (data.phylotree) {
        setNewick(data.phylotree);
      } else {
        setError("No phylogenetic tree was generated (fewer than 2 sequences?)");
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = reader.result as string;
      setNewickText(text);
      setNewick(text);
    };
    reader.readAsText(file);
  }

  function handlePasteNewick() {
    if (!newickText.trim()) { setError("Paste a Newick tree string first."); return; }
    setNewick(newickText.trim());
    setError(null);
  }

  const DEMO_FASTA = `>seq1
MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGLNGTVNLFGQTVDDLYKLLPENNVLSPLPSQAMDDLML
>seq2
MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPVAPTPAAPAPAPSWPLSSSVPSQKTYQGLNGTVNLFGQTVDDLYKLLPENNVLSPLPSQAMDDLML`;

  return (
    <div className="max-w-4xl mx-auto p-6">
      <Link href="/analyze" className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition mb-6">
        <ArrowLeft className="w-4 h-4" /> Choose a different operation
      </Link>

      <div className="flex items-center gap-4 mb-6">
        <div className="p-3 rounded-xl bg-accent-cyan/10">
          <GitFork className="w-6 h-6 text-accent-cyan" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Phylogenetic Tree</h1>
          <p className="text-sm text-text-secondary">Build trees from sequences or visualize existing Newick trees</p>
        </div>
      </div>

      {/* Mode toggle */}
      <div className="flex gap-2 mb-6">
        <button onClick={() => setMode("align")}
          className={`px-4 py-2 rounded-xl text-sm border transition ${mode === "align" ? "border-accent-cyan bg-accent-cyan/10 text-accent-cyan" : "border-glass-border text-text-muted hover:text-text-primary"}`}>
          Align Sequences
        </button>
        <button onClick={() => setMode("upload")}
          className={`px-4 py-2 rounded-xl text-sm border transition ${mode === "upload" ? "border-accent-cyan bg-accent-cyan/10 text-accent-cyan" : "border-glass-border text-text-muted hover:text-text-primary"}`}>
          Upload Tree
        </button>
      </div>

      {/* Input */}
      {mode === "align" ? (
        <div className="glass-card p-6 mb-6">
          <h2 className="text-sm font-semibold text-text-primary mb-2">Input Sequences (FASTA)</h2>
          <p className="text-xs text-text-muted mb-3">Paste two or more protein sequences in FASTA format. A multiple sequence alignment will be computed via Clustal Omega, then the phylogenetic tree is extracted.</p>
          <button onClick={() => setFasta(DEMO_FASTA)}
            className="px-3 py-1 text-xs rounded-full bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan hover:bg-accent-cyan/20 transition mb-3">
            Load demo (p53 variants)
          </button>
          <textarea value={fasta} onChange={e => setFasta(e.target.value)}
            rows={8}
            placeholder=">sequence1&#10;MEEPQSDPSVEPPLSQETFSDLWKLLPENN...&#10;>sequence2&#10;MEEPQSDPSVEPPLSQETFSDLWKLLPENN..."
            className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition font-mono text-sm resize-none bg-surface-1 text-text-primary"
          />
          {error && <p className="text-error text-sm mt-2">{error}</p>}
          <button onClick={handleBuildTree} disabled={loading}
            className="w-full btn-primary py-2.5 flex items-center justify-center gap-2 mt-3 disabled:opacity-40">
            {loading ? <><LoaderCircle className="w-4 h-4 animate-spin" /> Building&hellip;</> : <><GitFork className="w-4 h-4" /> Build Tree</>}
          </button>
        </div>
      ) : (
        <div className="glass-card p-6 mb-6">
          <h2 className="text-sm font-semibold text-text-primary mb-2">Upload or Paste Newick Tree</h2>
          <input ref={fileRef} type="file" accept=".nwk,.newick,.tree,.txt" onChange={handleFileUpload} className="hidden" />
          <button onClick={() => fileRef.current?.click()}
            className="flex items-center gap-2 px-4 py-2 rounded-xl border border-glass-border text-sm text-text-secondary hover:text-text-primary hover:border-accent-cyan/40 transition mb-3">
            <Upload className="w-4 h-4" /> Upload Newick file
          </button>
          <textarea value={newickText} onChange={e => setNewickText(e.target.value)}
            rows={5}
            placeholder="(seq1:0.1,seq2:0.2,(seq3:0.3,seq4:0.4):0.5);"
            className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition font-mono text-sm resize-none bg-surface-1 text-text-primary"
          />
          {error && <p className="text-error text-sm mt-2">{error}</p>}
          <button onClick={handlePasteNewick}
            className="w-full btn-primary py-2.5 flex items-center justify-center gap-2 mt-3">
            <FileText className="w-4 h-4" /> Visualize Tree
          </button>
        </div>
      )}

      {/* Result */}
      {newick && (
        <div className="glass-card p-6">
          <h2 className="text-sm font-semibold text-text-primary mb-3">Tree Visualization</h2>
          <PhyloTreeViewer newick={newick} />
        </div>
      )}
    </div>
  );
}
