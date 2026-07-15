'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { DockingInteraction } from '@/lib/api';

interface DockingViewerProps {
  pdbId: string;
  ligandPdb: string;
  interactions?: DockingInteraction;
  height?: number | string;
  backgroundColor?: string;
}

type StyleMode = 'cartoon' | 'surface' | 'stick';

interface PDBeElement extends HTMLElement {
  plugin?: {
    loadStructureFromData: (data: string, format: string, options?: Record<string, unknown>) => Promise<unknown>;
    canvas3d?: {
      requestDraw: () => void;
      camera: {
        spin: (on: boolean | string, speed?: number) => void;
        reset: () => void;
      };
    };
    primitives?: {
      clear: () => void;
      add: (primitives: unknown[]) => void;
    };
  };
}

export function DockingViewer({
  pdbId,
  ligandPdb,
  interactions,
  height = 480,
  backgroundColor = '#0d1117',
}: DockingViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<PDBeElement | null>(null);
  const initRef = useRef(false);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const [styleMode] = useState<StyleMode>('cartoon');
  const [spinning, setSpinning] = useState(false);

  const drawInteractions = useCallback((inter: DockingInteraction) => {
    const plugin = viewerRef.current?.plugin;
    if (!plugin?.primitives) return;

    try {
      plugin.primitives.clear();
      const primitives: unknown[] = [];

      for (const hb of inter.hbonds || []) {
        if (hb.ligand_coords && hb.protein_coords) {
          primitives.push({
            kind: 'cylinder',
            start: { x: hb.ligand_coords[0], y: hb.ligand_coords[1], z: hb.ligand_coords[2] },
            end: { x: hb.protein_coords[0], y: hb.protein_coords[1], z: hb.protein_coords[2] },
            color: 0x4488ff,
            radius: 0.15,
          });
        }
      }

      for (const hp of inter.hydrophobic || []) {
        if (hp.ligand_coords && hp.protein_coords) {
          primitives.push({
            kind: 'cylinder',
            start: { x: hp.ligand_coords[0], y: hp.ligand_coords[1], z: hp.ligand_coords[2] },
            end: { x: hp.protein_coords[0], y: hp.protein_coords[1], z: hp.protein_coords[2] },
            color: 0xff8844,
            radius: 0.12,
          });
        }
      }

      for (const ps of inter.pi_stacking || []) {
        if (ps.ring_centroid && ps.ligand_centroid) {
          primitives.push({
            kind: 'cylinder',
            start: { x: ps.ring_centroid[0], y: ps.ring_centroid[1], z: ps.ring_centroid[2] },
            end: { x: ps.ligand_centroid[0], y: ps.ligand_centroid[1], z: ps.ligand_centroid[2] },
            color: 0xff44ff,
            radius: 0.18,
          });
        }
      }

      for (const sb of inter.salt_bridges || []) {
        if (sb.ligand_coords && sb.protein_coords) {
          primitives.push({
            kind: 'cylinder',
            start: { x: sb.ligand_coords[0], y: sb.ligand_coords[1], z: sb.ligand_coords[2] },
            end: { x: sb.protein_coords[0], y: sb.protein_coords[1], z: sb.protein_coords[2] },
            color: 0x00cccc,
            radius: 0.2,
          });
        }
      }

      if (primitives.length > 0) {
        plugin.primitives.add(primitives);
      }
      plugin.canvas3d?.requestDraw();
    } catch {
      // Interaction drawing is best-effort
    }
  }, []);

  // Initialize viewer ONCE per pdbId — never re-create
  useEffect(() => {
    if (!pdbId || !ligandPdb) {
      setStatus('error');
      setError('Missing structure data');
      return;
    }

    const container = containerRef.current;
    if (!container) return;

    // Prevent double-init (React StrictMode)
    if (initRef.current) return;
    initRef.current = true;

    let cancelled = false;
    let checkInterval: ReturnType<typeof setInterval> | null = null;

    // Create the pdbe-molstar web component
    container.innerHTML = '';

    const el = document.createElement('pdbe-molstar') as PDBeElement;
    el.setAttribute('molecule-id', pdbId.toLowerCase());
    el.setAttribute('hide-controls', '');
    el.setAttribute('background-color', backgroundColor);
    el.id = `pdbe-docking-${pdbId.toLowerCase()}`;
    container.appendChild(el);
    viewerRef.current = el;

    // Wait for pdbe-molstar to finish loading models via its custom event
    let cancelled_after_event = false;

    const onModelsLoaded = async () => {
      if (cancelled || cancelled_after_event) return;
      cancelled_after_event = true;
      if (checkInterval) clearInterval(checkInterval);

      const plugin = el.plugin;
      if (!plugin) {
        if (!cancelled) { setStatus('ready'); }
        return;
      }

      // Load ligand as additional structure
      if (ligandPdb) {
        try {
          await plugin.loadStructureFromData(ligandPdb, 'pdb', {});
        } catch {
          // Best-effort
        }
      }

      // Draw interaction lines
      if (interactions) {
        drawInteractions(interactions);
      }

      if (!cancelled) {
        setStatus('ready');
      }
    };

    el.addEventListener('molstar-models-loaded', onModelsLoaded);

    // Fallback polling: check if plugin exists at all (not canvas3d which may be renamed)
    let attempts = 0;
    checkInterval = setInterval(() => {
      if (cancelled || cancelled_after_event) {
        if (checkInterval) clearInterval(checkInterval);
        return;
      }
      // Check if the web component has rendered anything (canvas element present)
      const hasCanvas = el.querySelector('canvas');
      if (hasCanvas) {
        onModelsLoaded();
        return;
      }
      attempts++;
      if (attempts > 100) { // 30 seconds max
        if (checkInterval) clearInterval(checkInterval);
        // Even if we can't detect it, mark ready — the viewer may be working
        if (!cancelled) {
          setStatus('ready');
        }
      }
    }, 300);

    return () => {
      cancelled = true;
      cancelled_after_event = true;
      if (checkInterval) clearInterval(checkInterval);
      el.removeEventListener('molstar-models-loaded', onModelsLoaded);
    };
  }, [pdbId, ligandPdb, backgroundColor]); // NO interactions here — avoids re-init

  // Update interactions without re-creating viewer
  useEffect(() => {
    if (status === 'ready' && interactions) {
      drawInteractions(interactions);
    }
  }, [interactions, status, drawInteractions]);

  // Spin control
  useEffect(() => {
    const plugin = viewerRef.current?.plugin;
    if (!plugin?.canvas3d?.camera) return;
    plugin.canvas3d.camera.spin(spinning ? 'y' : false);
  }, [spinning, status]);

  return (
    <div className="w-full rounded-lg border border-white/10 bg-[#0d1117]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 px-3 py-2">
        <span className="font-mono text-xs text-white/60">Docking pose — {pdbId}</span>
        <div className="flex items-center gap-2">
          <select
            value={styleMode}
            onChange={() => {}}
            disabled={status !== 'ready'}
            className="rounded border border-white/10 bg-black/30 px-2 py-1 text-xs text-white/80 disabled:opacity-40"
          >
            <option value="cartoon">Cartoon</option>
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

      {status === 'ready' && interactions && (
        <div className="flex flex-wrap items-center gap-3 border-b border-white/10 px-3 py-1.5 text-[10px]">
          {interactions.hbonds?.length > 0 && (
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-[#4488ff]" /> H-bonds ({interactions.hbonds.length})</span>
          )}
          {interactions.hydrophobic?.length > 0 && (
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-[#ff8844]" /> Hydrophobic ({interactions.hydrophobic.length})</span>
          )}
          {interactions.pi_stacking?.length > 0 && (
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-[#ff44ff]" /> Pi-stacking ({interactions.pi_stacking.length})</span>
          )}
          {interactions.salt_bridges?.length > 0 && (
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-[#00cccc]" /> Salt bridges ({interactions.salt_bridges.length})</span>
          )}
        </div>
      )}

      <div ref={containerRef} style={{ height, minHeight: height, position: 'relative' }} />
      {status === 'loading' && (
        <div className="flex items-center justify-center py-4 text-sm text-white/60">
          Loading structure...
        </div>
      )}
      {status === 'error' && (
        <div className="flex items-center justify-center py-4 px-6 text-center text-sm text-red-400">
          {error}
        </div>
      )}
    </div>
  );
}
