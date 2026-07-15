'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { DockingInteraction } from '@/lib/api';
import {
  RotateCcw, RotateCw, Camera, FlipHorizontal, Palette,
  Box, Layers, Minus, Circle, Hexagon
} from 'lucide-react';

interface DockingViewerProps {
  pdbId: string;
  ligandPdb: string;
  interactions?: DockingInteraction;
  height?: number | string;
  backgroundColor?: string;
}

type RepresentationType = 'cartoon' | 'ball-and-stick' | 'spacefill' | 'gaussian-surface' | 'molecular-surface' | 'putty' | 'ribbon';
type ColorScheme = 'spectrum' | 'chain' | 'secondary-structure' | 'residue-type' | 'bfactor' | 'uniform';
type InteractionLayer = 'hbonds' | 'hydrophobic' | 'pi_stacking' | 'salt_bridges';

const INTERACTION_LAYERS: { key: InteractionLayer; label: string; color: string }[] = [
  { key: 'hbonds', label: 'H-bonds', color: '#4488ff' },
  { key: 'hydrophobic', label: 'Hydrophobic', color: '#ff8844' },
  { key: 'pi_stacking', label: 'Pi-stacking', color: '#ff44ff' },
  { key: 'salt_bridges', label: 'Salt bridges', color: '#00cccc' },
];

const REP_OPTIONS: { value: RepresentationType; label: string; icon: typeof Box }[] = [
  { value: 'cartoon', label: 'Cartoon', icon: Layers },
  { value: 'ribbon', label: 'Ribbon', icon: Minus },
  { value: 'ball-and-stick', label: 'Ball+Stick', icon: Box },
  { value: 'spacefill', label: 'Spacefill', icon: Circle },
  { value: 'gaussian-surface', label: 'Surface', icon: Hexagon },
  { value: 'putty', label: 'Putty', icon: Minus },
];

const COLOR_MAP: Record<ColorScheme, Record<string, unknown>> = {
  'spectrum': { name: 'spectrum' },
  'chain': { name: 'chain-id' },
  'secondary-structure': { name: 'secondary-structure' },
  'residue-type': { name: 'residue-type' },
  'bfactor': { name: 'bfactor' },
  'uniform': { name: 'uniform', value: 0x66ccff },
};

interface PDBeElement extends HTMLElement {
  viewerInstance?: {
    plugin?: {
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
    visual: {
      update: (options: Record<string, unknown>, fullLoad?: boolean) => Promise<boolean>;
      select: (params: Record<string, unknown>) => Promise<void>;
      reset: (params: Record<string, unknown>) => Promise<void>;
      toggleSpin: (spin?: boolean) => Promise<void>;
      focus: (selection: unknown[]) => Promise<void>;
    };
    clear: () => Promise<void>;
    load: (params: Record<string, unknown>, fullLoad?: boolean) => Promise<void>;
    deleteStructure: (id?: string | number) => Promise<void>;
    events: {
      loadComplete: { subscribe: (cb: (success: boolean) => void) => void };
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
  const [representation, setRepresentation] = useState<RepresentationType>('cartoon');
  const [colorScheme, setColorScheme] = useState<ColorScheme>('spectrum');
  const [spinning, setSpinning] = useState(false);
  const [visibleInteractions, setVisibleInteractions] = useState<Record<InteractionLayer, boolean>>({
    hbonds: true,
    hydrophobic: true,
    pi_stacking: true,
    salt_bridges: true,
  });
  const representationRef = useRef<RepresentationType>('cartoon');
  const colorSchemeRef = useRef<ColorScheme>('spectrum');

  const applyVisualization = useCallback(async (rep: RepresentationType, color: ColorScheme) => {
    const viewer = viewerRef.current?.viewerInstance;
    if (!viewer) return;

    try {
      await viewer.visual.update({
        moleculeId: pdbId.toLowerCase(),
        visualStyle: {
          polymer: { type: rep, color: { name: COLOR_MAP[color].name } },
          het: 'ball-and-stick',
          water: 'spacefill',
        },
      }, true);
    } catch {
      // Best-effort
    }
  }, [pdbId]);

  const loadLigand = useCallback(async () => {
    const viewer = viewerRef.current?.viewerInstance;
    if (!viewer || !ligandPdb) return;

    try {
      const blob = new Blob([ligandPdb], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);

      await viewer.load({
        url,
        format: 'pdb',
        id: 'ligand',
      }, false);

      URL.revokeObjectURL(url);
    } catch {
      // Best-effort
    }
  }, [ligandPdb]);

  const drawInteractions = useCallback((inter: DockingInteraction, visible: Record<InteractionLayer, boolean>) => {
    const plugin = viewerRef.current?.viewerInstance?.plugin;
    if (!plugin?.primitives) return;

    try {
      plugin.primitives.clear();
      const primitives: unknown[] = [];

      for (const hb of visible.hbonds ? inter.hbonds || [] : []) {
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

      for (const hp of visible.hydrophobic ? inter.hydrophobic || [] : []) {
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

      for (const ps of visible.pi_stacking ? inter.pi_stacking || [] : []) {
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

      for (const sb of visible.salt_bridges ? inter.salt_bridges || [] : []) {
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

  const handleScreenshot = useCallback(() => {
    const canvas = viewerRef.current?.querySelector('canvas');
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = `docking-${pdbId}-${Date.now()}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  }, [pdbId]);

  const handleResetCamera = useCallback(() => {
    viewerRef.current?.viewerInstance?.visual?.reset({ camera: true });
  }, []);

  const handleFlipView = useCallback(() => {
    const cam = viewerRef.current?.viewerInstance?.plugin?.canvas3d?.camera;
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

      const viewer = el.viewerInstance;
      if (!viewer) {
        if (!cancelled) setStatus('ready');
        return;
      }

      // Load ligand as separate structure
      await loadLigand();

      // Draw interaction lines
      if (interactions) drawInteractions(interactions, visibleInteractions);

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

  // Representation + color changes
  useEffect(() => {
    if (status === 'ready' && (representation !== representationRef.current || colorScheme !== colorSchemeRef.current)) {
      representationRef.current = representation;
      colorSchemeRef.current = colorScheme;
      applyVisualization(representation, colorScheme);
    }
  }, [representation, colorScheme, status, applyVisualization]);

  // Interaction updates
  useEffect(() => {
    if (status === 'ready' && interactions) {
      drawInteractions(interactions, visibleInteractions);
    }
  }, [interactions, status, drawInteractions, visibleInteractions]);

  // Spin
  useEffect(() => {
    viewerRef.current?.viewerInstance?.visual?.toggleSpin(spinning);
  }, [spinning, status]);

  return (
    <div className="w-full rounded-lg border border-white/10 bg-[#0d1117] relative z-20">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-white/10 px-3 py-2 relative z-20">
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
            <option value="spectrum">Spectrum</option>
            <option value="chain">Chain</option>
            <option value="secondary-structure">Sec. Structure</option>
            <option value="residue-type">Residue Type</option>
            <option value="bfactor">B-factor</option>
            <option value="uniform">Uniform</option>
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
          <RotateCw className="w-3.5 h-3.5" />
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
        <div className="flex flex-wrap items-center gap-2 border-b border-white/10 px-3 py-2 text-[10px]">
          <span className="mr-1 text-white/40">Contacts</span>
          {INTERACTION_LAYERS.map(({ key, label, color }) => {
            const count = interactions[key]?.length || 0;
            if (!count) return null;
            const active = visibleInteractions[key];
            return (
              <button
                key={key}
                type="button"
                aria-pressed={active}
                onClick={() => setVisibleInteractions(current => ({ ...current, [key]: !current[key] }))}
                className={`flex items-center gap-1 rounded px-1.5 py-1 transition ${active ? 'bg-white/10 text-white/90' : 'text-white/35 line-through'}`}
              >
                <span className="inline-block w-3 h-0.5" style={{ backgroundColor: color }} />
                {label} ({count})
              </button>
            );
          })}
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
