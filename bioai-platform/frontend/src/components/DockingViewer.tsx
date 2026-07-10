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

const SCRIPT_URL = 'https://3Dmol.org/build/3Dmol-min.js';

function load3Dmol(): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('3Dmol can only run in the browser'));
  if (window.$3Dmol) return Promise.resolve();
  return new Promise((resolve, reject) => {
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
}

interface DockingViewerProps {
  pdbId: string;
  ligandPdb: string;
  height?: number | string;
  backgroundColor?: string;
}

type StyleMode = 'cartoon' | 'surface' | 'stick';

export function DockingViewer({ pdbId, ligandPdb, height = 480, backgroundColor = '#0d1117' }: DockingViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<MoleViewer | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const [styleMode, setStyleMode] = useState<StyleMode>('cartoon');
  const [spinning, setSpinning] = useState(false);

  const buildScene = useCallback(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.clear();

    const protUrl = `https://files.rcsb.org/download/${pdbId}.pdb`;
    fetch(protUrl)
      .then((r) => {
        if (!r.ok) throw new Error(`Protein fetch failed (HTTP ${r.status})`);
        return r.text();
      })
      .then((pdbData) => {
        viewer.addModel(pdbData, 'pdb');

        if (ligandPdb) {
          viewer.addModel(ligandPdb, 'pdb');
        }

        viewer.setStyle({}, { cartoon: { color: 'spectrum' } });
        viewer.setStyle({ model: -1 }, { stick: { colorscheme: { prop: 'elem', map: { C: '#66ccff', N: '#ff66cc', O: '#ff4444', S: '#ffcc00' } } } });

        if (ligandPdb) {
          viewer.addLabel('Ligand', {
            position: { x: 0, y: 0, z: 0 },
            fontSize: 12,
            fontColor: 'white',
            backgroundColor: 'rgba(0,0,0,0.5)',
            showBackground: true,
          });
        }

        viewer.zoomTo();
        viewer.render();
        setStatus('ready');
      })
      .catch((err: Error) => {
        setError(err.message);
        setStatus('error');
      });
  }, [pdbId, ligandPdb]);

  useEffect(() => {
    if (!pdbId || !ligandPdb) {
      setStatus('error');
      setError('Missing structure data');
      return;
    }

    let cancelled = false;
    setStatus('loading');
    setError(null);

    load3Dmol()
      .then(() => {
        if (cancelled || !containerRef.current) return;
        if (viewerRef.current) {
          viewerRef.current.clear();
        } else {
          viewerRef.current = window.$3Dmol.createViewer(containerRef.current, { backgroundColor });
        }
        buildScene();
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
        setStatus('error');
      });

    return () => { cancelled = true; };
  }, [pdbId, ligandPdb, backgroundColor, buildScene]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (spinning) viewer?.spin('y', 1);
    else viewer?.spin(false);
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
        <span className="font-mono text-xs text-white/60">Docking pose — {pdbId}</span>
        <div className="flex items-center gap-2">
          <select
            value={styleMode}
            onChange={(e) => setStyleMode(e.target.value as StyleMode)}
            disabled={status !== 'ready'}
            className="rounded border border-white/10 bg-black/30 px-2 py-1 text-xs text-white/80 disabled:opacity-40"
          >
            <option value="cartoon">Cartoon</option>
            <option value="surface">Surface</option>
            <option value="stick">Stick</option>
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
    </div>
  );
}
