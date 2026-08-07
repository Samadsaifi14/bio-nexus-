'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { DownloadSimple as Download } from '@phosphor-icons/react';
import { HudPanel, HudLegend, LegendItem } from '@/components/ui';
import { downloadText } from '@/lib/export-utils';

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
  backgroundColor = '#0B0C14',
}: AlphaFoldViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<MoleViewer | null>(null);
  const pdbTextRef = useRef<string | null>(null);

  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const [styleMode, setStyleMode] = useState<StyleMode>('confidence');
  const [spinning, setSpinning] = useState(false);

  const exportPdb = () => {
    if (!pdbTextRef.current) return;
    downloadText(pdbTextRef.current, `${uniprotId ?? 'structure'}.pdb`);
  };

  const exportPng = () => {
    const canvas = containerRef.current?.querySelector<HTMLCanvasElement>('canvas');
    if (!canvas) return;
    const a = document.createElement('a');
    a.download = `${uniprotId ?? 'structure'}.png`;
    a.href = canvas.toDataURL('image/png');
    a.click();
  };

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
        pdbTextRef.current = pdbData;
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
    <div className="relative w-full overflow-hidden rounded-xl border border-glass-border bg-[#0B0C14]">
      {/* HUD toolbar — floats in the viewer's space, near-opaque */}
      <HudPanel className="absolute left-3 right-3 top-3 z-10 flex flex-wrap items-center justify-between gap-2 px-3 py-2">
        <span className="font-mono text-xs text-text-muted">
          {uniprotId ? `AlphaFold model — ${uniprotId}` : 'AlphaFold model'}
        </span>

        <div className="flex items-center gap-2">
          <select
            value={styleMode}
            onChange={(e) => setStyleMode(e.target.value as StyleMode)}
            disabled={status !== 'ready'}
            className="rounded-md border border-glass-border bg-black/40 px-2 py-1 text-xs text-text-secondary outline-none disabled:opacity-40 focus:border-accent-cyan/40"
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
            className="rounded-md border border-glass-border bg-black/40 px-2 py-1 text-xs text-text-secondary hover:bg-black/60 hover:text-text-primary disabled:opacity-40 transition-colors"
          >
            {spinning ? 'Stop spin' : 'Spin'}
          </button>
          <button
            type="button"
            onClick={exportPdb}
            disabled={status !== 'ready'}
            title="Download structure as PDB"
            className="rounded-md border border-glass-border bg-black/40 px-2 py-1 text-xs text-text-secondary hover:bg-black/60 hover:text-text-primary disabled:opacity-40 transition-colors flex items-center gap-1"
          >
            <Download className="w-3.5 h-3.5" /> PDB
          </button>
          <button
            type="button"
            onClick={exportPng}
            disabled={status !== 'ready'}
            title="Download current view as PNG"
            className="rounded-md border border-glass-border bg-black/40 px-2 py-1 text-xs text-text-secondary hover:bg-black/60 hover:text-text-primary disabled:opacity-40 transition-colors flex items-center gap-1"
          >
            <Download className="w-3.5 h-3.5" /> PNG
          </button>
        </div>
      </HudPanel>

      <div className="relative" style={{ height }}>
        <div ref={containerRef} className="absolute inset-0" />

        {status === 'loading' && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0B0C14]/80 text-sm text-text-secondary">
            Loading structure...
          </div>
        )}

        {status === 'error' && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0B0C14]/90 px-6 text-center text-sm text-error">
            {error}
          </div>
        )}

        {/* Corner-anchored, near-opaque legend — never blurred over the model */}
        {status === 'ready' && styleMode !== 'spectrum' && (
          <HudLegend title="pLDDT confidence" className="absolute bottom-3 left-3 z-10 max-w-[calc(100%-1.5rem)]">
            {CONFIDENCE_BANDS.map((band) => (
              <LegendItem key={band.label} color={band.color} label={band.label} />
            ))}
          </HudLegend>
        )}
      </div>
    </div>
  );
}
