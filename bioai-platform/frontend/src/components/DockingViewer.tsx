'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { DockingInteraction } from '@/lib/api';
import {
  RotateCcw, Camera, FlipHorizontal, Palette,
  Box, Layers, Minus, Circle, Hexagon
} from 'lucide-react';

interface DockingViewerProps {
  pdbId: string;
  ligandPdb: string;
  interactions?: DockingInteraction;
  height?: number | string;
  backgroundColor?: string;
}

type RepresentationType = 'cartoon' | 'ball-and-stick' | 'spacefill' | 'surface' | 'ribbon' | 'tube';
type ColorScheme = 'spectrum' | 'chain' | 'secondary-structure' | 'residue-type' | 'bfactor' | 'uniform';

const REP_OPTIONS: { value: RepresentationType; label: string; icon: typeof Box }[] = [
  { value: 'cartoon', label: 'Cartoon', icon: Layers },
  { value: 'ribbon', label: 'Ribbon', icon: Minus },
  { value: 'ball-and-stick', label: 'Ball+Stick', icon: Box },
  { value: 'spacefill', label: 'Spacefill', icon: Circle },
  { value: 'surface', label: 'Surface', icon: Hexagon },
  { value: 'tube', label: 'Tube', icon: Minus },
];

const COLOR_OPTIONS: { value: ColorScheme; label: string }[] = [
  { value: 'spectrum', label: 'Spectrum' },
  { value: 'chain', label: 'Chain' },
  { value: 'secondary-structure', label: 'Sec. Structure' },
  { value: 'residue-type', label: 'Residue Type' },
  { value: 'bfactor', label: 'B-factor' },
  { value: 'uniform', label: 'Uniform' },
];

interface PDBeElement extends HTMLElement {
  plugin?: {
    loadStructureFromData: (data: string, format: string, options?: Record<string, unknown>) => Promise<unknown>;
    clear: () => void;
    build: () => unknown;
    canvas3d?: {
      requestDraw: () => void;
      camera: {
        spin: (on: boolean | string, speed?: number) => void;
        reset: () => void;
        focus: (options: unknown) => void;
      };
    };
    primitives?: {
      clear: () => void;
      add: (primitives: unknown[]) => void;
    };
    managers?: {
      structure?: {
        hierarchy?: {
          current?: {
            structures?: Array<{ representations?: unknown[] }>;
          };
        };
      };
    };
  };
}

const REPRESENTATION_MAP: Record<RepresentationType, Record<string, unknown>> = {
  'cartoon': { type: 'cartoon', quality: 'medium' },
  'ribbon': { type: 'ribbon', quality: 'medium' },
  'ball-and-stick': { type: 'ball-and-stick' },
  'spacefill': { type: 'spacefill' },
  'surface': { type: 'surface', probeRadius: 1.4, opacity: 0.85 },
  'tube': { type: 'tube', radius: 1.2 },
};

const COLOR_MAP: Record<ColorScheme, Record<string, unknown>> = {
  'spectrum': { name: 'spectrum' },
  'chain': { name: 'chain-id' },
  'secondary-structure': { name: 'secondary-structure' },
  'residue-type': { name: 'residue-type' },
  'bfactor': { name: 'bfactor', coloringParams: { domain: [0, 100] } },
  'uniform': { name: 'uniform', value: 0x66ccff },
};

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
  const pdbDataRef = useRef<string>('');
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const [representation, setRepresentation] = useState<RepresentationType>('cartoon');
  const [colorScheme, setColorScheme] = useState<ColorScheme>('spectrum');
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
      // Best-effort
    }
  }, []);

  const applyVisualization = useCallback(async (rep: RepresentationType, color: ColorScheme) => {
    const el = viewerRef.current;
    const plugin = el?.plugin;
    if (!plugin || !pdbDataRef.current) return;

    try {
      plugin.clear();

      const repConfig = REPRESENTATION_MAP[rep];
      const colorConfig = COLOR_MAP[color];

      await plugin.loadStructureFromData(pdbDataRef.current, 'pdb', {
        representation: {
          ...repConfig,
          color: colorConfig,
        },
      });

      if (ligandPdb) {
        await plugin.loadStructureFromData(ligandPdb, 'pdb', {
          representation: {
            type: 'ball-and-stick',
            color: { name: 'uniform', value: 0xffcc00 },
          },
        });
      }

      if (interactions) {
        drawInteractions(interactions);
      }
    } catch {
      // Best-effort
    }
  }, [ligandPdb, interactions, drawInteractions]);

  const handleScreenshot = useCallback(() => {
    const el = viewerRef.current;
    const canvas = el?.querySelector('canvas');
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = `docking-${pdbId}-${Date.now()}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  }, [pdbId]);

  const handleResetCamera = useCallback(() => {
    viewerRef.current?.plugin?.canvas3d?.camera?.reset();
  }, []);

  const handleFlipView = useCallback(() => {
    const cam = viewerRef.current?.plugin?.canvas3d?.camera;
    if (!cam) return;
    cam.spin('x');
    setTimeout(() => cam.spin(false), 1500);
  }, []);

  // Initialize viewer ONCE per pdbId
  useEffect(() => {
    if (!pdbId || !ligandPdb) {
      setStatus('error');
      setError('Missing structure data');
      return;
    }

    const container = containerRef.current;
    if (!container) return;
    if (initRef.current) return;
    initRef.current = true;

    let cancelled = false;
    let checkInterval: ReturnType<typeof setInterval> | null = null;

    container.innerHTML = '';

    const el = document.createElement('pdbe-molstar') as PDBeElement;
    el.setAttribute('molecule-id', pdbId.toLowerCase());
    el.setAttribute('hide-controls', '');
    el.setAttribute('background-color', backgroundColor);
    el.id = `pdbe-docking-${pdbId.toLowerCase()}`;
    container.appendChild(el);
    viewerRef.current = el;

    let cancelled_after_event = false;

    const onModelsLoaded = async () => {
      if (cancelled || cancelled_after_event) return;
      cancelled_after_event = true;
      if (checkInterval) clearInterval(checkInterval);

      const plugin = el.plugin;
      if (!plugin) {
        if (!cancelled) setStatus('ready');
        return;
      }

      // Store protein PDB data for re-renders
      try {
        const pdbUrl = `https://files.rcsb.org/download/${pdbId}.pdb`;
        const res = await fetch(pdbUrl);
        if (res.ok) pdbDataRef.current = await res.text();
      } catch {
        // Best-effort
      }

      // Load ligand as ball-and-stick (always visible, distinct color)
      if (ligandPdb) {
        try {
          await plugin.loadStructureFromData(ligandPdb, 'pdb', {
            representation: {
              type: 'ball-and-stick',
              color: { name: 'uniform', value: 0xffcc00 },
            },
          });
        } catch {
          // Best-effort
        }
      }

      if (interactions) drawInteractions(interactions);
      if (!cancelled) setStatus('ready');
    };

    el.addEventListener('molstar-models-loaded', onModelsLoaded);

    let attempts = 0;
    checkInterval = setInterval(() => {
      if (cancelled || cancelled_after_event) {
        if (checkInterval) clearInterval(checkInterval);
        return;
      }
      const hasCanvas = el.querySelector('canvas');
      if (hasCanvas) {
        onModelsLoaded();
        return;
      }
      attempts++;
      if (attempts > 100) {
        if (checkInterval) clearInterval(checkInterval);
        if (!cancelled) setStatus('ready');
      }
    }, 300);

    return () => {
      cancelled = true;
      cancelled_after_event = true;
      if (checkInterval) clearInterval(checkInterval);
      el.removeEventListener('molstar-models-loaded', onModelsLoaded);
    };
  }, [pdbId, ligandPdb, backgroundColor]); // eslint-disable-line react-hooks/exhaustive-deps

  // Representation/color changes
  useEffect(() => {
    if (status === 'ready') {
      applyVisualization(representation, colorScheme);
    }
  }, [representation, colorScheme]); // eslint-disable-line react-hooks/exhaustive-deps

  // Interaction updates
  useEffect(() => {
    if (status === 'ready' && interactions) {
      drawInteractions(interactions);
    }
  }, [interactions, status, drawInteractions]);

  // Spin
  useEffect(() => {
    const cam = viewerRef.current?.plugin?.canvas3d?.camera;
    if (!cam) return;
    cam.spin(spinning ? 'y' : false);
  }, [spinning, status]);

  return (
    <div className="w-full rounded-lg border border-white/10 bg-[#0d1117]">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-white/10 px-3 py-2">
        <span className="font-mono text-xs text-white/60 mr-2">{pdbId}</span>

        {/* Representation */}
        <div className="flex items-center gap-1">
          {REP_OPTIONS.map(opt => {
            const Icon = opt.icon;
            return (
              <button
                key={opt.value}
                type="button"
                title={opt.label}
                onClick={() => setRepresentation(opt.value)}
                disabled={status !== 'ready'}
                className={`p-1.5 rounded text-[10px] transition disabled:opacity-40 ${
                  representation === opt.value
                    ? 'bg-accent-cyan/20 text-accent-cyan'
                    : 'text-white/50 hover:text-white/80 hover:bg-white/5'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
              </button>
            );
          })}
        </div>

        <div className="w-px h-5 bg-white/10" />

        {/* Color scheme */}
        <div className="relative">
          <select
            value={colorScheme}
            onChange={(e) => setColorScheme(e.target.value as ColorScheme)}
            disabled={status !== 'ready'}
            title="Color scheme"
            className="appearance-none rounded border border-white/10 bg-black/30 pl-6 pr-2 py-1 text-[10px] text-white/80 disabled:opacity-40 cursor-pointer"
          >
            {COLOR_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <Palette className="absolute left-1.5 top-1/2 -translate-y-1/2 w-3 h-3 text-white/40 pointer-events-none" />
        </div>

        <div className="w-px h-5 bg-white/10" />

        {/* Action buttons */}
        <button
          type="button"
          title="Toggle spin"
          onClick={() => setSpinning(s => !s)}
          disabled={status !== 'ready'}
          className={`p-1.5 rounded transition disabled:opacity-40 ${
            spinning ? 'text-accent-cyan bg-accent-cyan/10' : 'text-white/50 hover:text-white/80 hover:bg-white/5'
          }`}
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>

        <button
          type="button"
          title="Reset camera"
          onClick={handleResetCamera}
          disabled={status !== 'ready'}
          className="p-1.5 rounded text-white/50 hover:text-white/80 hover:bg-white/5 transition disabled:opacity-40"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>

        <button
          type="button"
          title="Flip view (X-axis)"
          onClick={handleFlipView}
          disabled={status !== 'ready'}
          className="p-1.5 rounded text-white/50 hover:text-white/80 hover:bg-white/5 transition disabled:opacity-40"
        >
          <FlipHorizontal className="w-3.5 h-3.5" />
        </button>

        <button
          type="button"
          title="Screenshot"
          onClick={handleScreenshot}
          disabled={status !== 'ready'}
          className="p-1.5 rounded text-white/50 hover:text-white/80 hover:bg-white/5 transition disabled:opacity-40"
        >
          <Camera className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Interaction legend */}
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

      {/* Canvas */}
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
