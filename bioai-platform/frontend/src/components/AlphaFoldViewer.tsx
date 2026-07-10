'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

interface MoleViewer {
  setStyle: (sel: Record<string, unknown>, style: Record<string, unknown>) => void;
  removeAllSurfaces: () => void;
  addSurface: (type: unknown, opts: Record<string, unknown>) => void;
  render: () => void;
  clear: () => void;
  addModel: (data: string, format: string) => void;
  zoomTo: () => void;
  spin: (axis: string | boolean, speed?: number) => void;
  resize: () => void;
  removeAllLabels: () => void;
  addLabel: (text: string, opts: Record<string, unknown>) => void;
}

interface MoleAtom {
  b: number;
  elem?: string;
  x?: number;
  y?: number;
  z?: number;
  serial?: number;
  resn?: string;
  resi?: number;
  chain?: string;
  [key: string]: unknown;
}

declare global {
  interface Window {
    $3Dmol: Record<string, unknown> & { createViewer: (el: HTMLElement, opts: Record<string, unknown>) => MoleViewer; SurfaceType: Record<string, unknown> };
  }
}

const SCRIPT_URL = 'https://3Dmol.org/build/3Dmol-min.js';

const CONFIDENCE_BANDS = [
  { label: 'Very high (pLDDT > 90)', color: '#0053D6' },
  { label: 'Confident (70–90)', color: '#65CBF3' },
  { label: 'Low (50–70)', color: '#FFDB13' },
  { label: 'Very low (< 50)', color: '#FF7D45' },
] as const;

function plddtColor(b: number): string {
  if (b > 90) return CONFIDENCE_BANDS[0].color;
  if (b > 70) return CONFIDENCE_BANDS[1].color;
  if (b > 50) return CONFIDENCE_BANDS[2].color;
  return CONFIDENCE_BANDS[3].color;
}

let scriptPromise: Promise<void> | null = null;

function load3Dmol(): Promise<void> {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('3Dmol can only run in the browser'));
  }
  if (window.$3Dmol) return Promise.resolve();
  if (scriptPromise) return scriptPromise;

  scriptPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT_URL}"]`);
    if (existing) {
      existing.addEventListener('load', () => resolve());
      existing.addEventListener('error', () => reject(new Error('Failed to load 3Dmol.js')));
      return;
    }
    const script = document.createElement('script');
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Failed to load 3Dmol.js'));
    document.head.appendChild(script);
  });

  return scriptPromise;
}

type StyleMode = 'confidence' | 'spectrum' | 'surface' | 'stick';

interface AlphaFoldViewerProps {
  pdbUrl?: string | null;
  uniprotId?: string;
  height?: number | string;
  backgroundColor?: string;
}

export function AlphaFoldViewer({
  pdbUrl,
  uniprotId,
  height = 420,
  backgroundColor = '#0d1117',
}: AlphaFoldViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<MoleViewer | null>(null);

  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const [styleMode, setStyleMode] = useState<StyleMode>('confidence');
  const [spinning, setSpinning] = useState(false);

  const applyStyle = useCallback((mode: StyleMode) => {
    const viewer = viewerRef.current;
    const $3Dmol = window.$3Dmol;
    if (!viewer || !$3Dmol) return;

    viewer.removeAllSurfaces();
    viewer.setStyle({}, {});

    switch (mode) {
      case 'confidence':
        viewer.setStyle({}, { cartoon: { colorfunc: (atom: MoleAtom) => plddtColor(atom.b) } });
        break;
      case 'spectrum':
        viewer.setStyle({}, { cartoon: { color: 'spectrum' } });
        break;
      case 'surface':
        viewer.setStyle({}, { cartoon: { colorfunc: (atom: MoleAtom) => plddtColor(atom.b) } });
        viewer.addSurface($3Dmol.SurfaceType.VDW, {
          opacity: 0.85,
          colorfunc: (atom: MoleAtom) => plddtColor(atom.b),
        });
        break;
      case 'stick':
        viewer.setStyle({}, { stick: { colorfunc: (atom: MoleAtom) => plddtColor(atom.b) } });
        break;
    }

    viewer.render();
  }, []);

  useEffect(() => {
    if (!pdbUrl) {
      setStatus('error');
      setError('No structure URL provided yet');
      return;
    }

    let cancelled = false;
    setStatus('loading');
    setError(null);

    load3Dmol()
      .then(() => fetch(pdbUrl))
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to fetch structure (HTTP ${res.status})`);
        return res.text();
      })
      .then((pdbData) => {
        if (cancelled || !containerRef.current) return;
        const $3Dmol = window.$3Dmol;

        if (viewerRef.current) {
          viewerRef.current.clear();
        } else {
          viewerRef.current = $3Dmol.createViewer(containerRef.current, { backgroundColor });
        }

        viewerRef.current.addModel(pdbData, 'pdb');
        applyStyle(styleMode);
        viewerRef.current.zoomTo();
        viewerRef.current.render();
        setStatus('ready');
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(
          err.message === 'Failed to fetch'
            ? 'Could not fetch the structure file (likely a CORS issue — see notes below)'
            : err.message
        );
        setStatus('error');
      });

    return () => {
      cancelled = true;
    };
  }, [pdbUrl, backgroundColor, applyStyle, styleMode]);

  useEffect(() => {
    if (status === 'ready') applyStyle(styleMode);
  }, [styleMode, status, applyStyle]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (spinning) viewer.spin('y', 1);
    else viewer.spin(false);
  }, [spinning, status]);

  useEffect(() => {
    const viewer = viewerRef.current;
    const container = containerRef.current;
    if (!viewer || !container) return;

    const observer = new ResizeObserver(() => viewer.resize());
    observer.observe(container);
    return () => observer.disconnect();
  }, [status]);

  return (
    <div className="w-full overflow-hidden rounded-lg border border-white/10 bg-[#0d1117]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 px-3 py-2">
        <span className="font-mono text-xs text-white/60">
          {uniprotId ? `AlphaFold model — ${uniprotId}` : 'AlphaFold model'}
        </span>

        <div className="flex items-center gap-2">
          <select
            value={styleMode}
            onChange={(e) => setStyleMode(e.target.value as StyleMode)}
            disabled={status !== 'ready'}
            className="rounded border border-white/10 bg-black/30 px-2 py-1 text-xs text-white/80 disabled:opacity-40"
          >
            <option value="confidence">Cartoon · pLDDT</option>
            <option value="spectrum">Cartoon · spectrum</option>
            <option value="surface">Surface · pLDDT</option>
            <option value="stick">Stick · pLDDT</option>
          </select>
          <button
            type="button"
            onClick={() => setSpinning((s) => !s)}
            disabled={status !== 'ready'}
            className="rounded border border-white/10 bg-black/30 px-2 py-1 text-xs text-white/80 hover:bg-black/50 disabled:opacity-40"
          >
            {spinning ? 'Stop spin' : 'Spin'}
          </button>
        </div>
      </div>

      <div className="relative" style={{ height }}>
        <div ref={containerRef} className="absolute inset-0" />

        {status === 'loading' && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0d1117]/80 text-sm text-white/60">
            Loading structure...
          </div>
        )}

        {status === 'error' && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0d1117]/90 px-6 text-center text-sm text-red-400">
            {error}
          </div>
        )}
      </div>

      {status === 'ready' && styleMode !== 'spectrum' && (
        <div className="flex flex-wrap items-center gap-3 border-t border-white/10 px-3 py-2 text-[11px] text-white/60">
          <span className="font-mono uppercase tracking-wide text-white/40">pLDDT confidence</span>
          {CONFIDENCE_BANDS.map((band) => (
            <span key={band.label} className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: band.color }} />
              {band.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
