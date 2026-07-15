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

declare global {
  interface Window {
    PDBeMolstarPlugin?: new () => PDBeMolstarInstance;
  }
}

interface PDBeMolstarInstance {
  render: (container: HTMLElement, options: Record<string, unknown>) => Promise<void>;
  plugin: {
    clear: () => void;
    build: () => unknown;
    loadStructureFromData: (data: string, format: string, options?: Record<string, unknown>) => Promise<unknown>;
    setSecurityContext: (ctx: unknown) => void;
    managers: {
      structure: {
        hierarchy: {
          current: {
            assemblies: Array<{ id: string }>;
          };
        };
      };
    };
    canvas3d: {
      requestDraw: () => void;
      camera: {
        focus: (snapshot: Record<string, unknown>) => void;
        reset: () => void;
        spin: (on: boolean) => void;
      };
    };
    state: {
      update: (state: unknown) => void;
    };
    update: (state: unknown) => void;
    primitives: {
      clear: () => void;
      add: (primitives: unknown[]) => void;
    };
    representation: {
      autoAttach: (structureRef: unknown) => void;
    };
    structures: {
      clear: () => void;
    };
  };
}

const CDN_URL = 'https://cdn.jsdelivr.net/npm/pdbe-molstar@3.12.0/build';

export function DockingViewer({
  pdbId,
  ligandPdb,
  interactions,
  height = 480,
  backgroundColor = '#0d1117',
}: DockingViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const pluginRef = useRef<PDBeMolstarInstance | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const [styleMode, setStyleMode] = useState<StyleMode>('cartoon');
  const [spinning, setSpinning] = useState(false);

  const buildScene = useCallback(async () => {
    const plugin = pluginRef.current;
    if (!plugin?.plugin) return;

    try {
      plugin.plugin.clear();

      // Load protein from RCSB
      const pdbUrl = `https://files.rcsb.org/download/${pdbId}.pdb`;
      const pdbRes = await fetch(pdbUrl);
      if (!pdbRes.ok) throw new Error(`Protein fetch failed (HTTP ${pdbRes.status})`);
      const pdbData = await pdbRes.text();

      // Load protein structure
      await plugin.plugin.loadStructureFromData(pdbData, 'pdb', {});

      // Load ligand structure
      if (ligandPdb) {
        await plugin.plugin.loadStructureFromData(ligandPdb, 'pdb', {});
      }

      // Apply styles
      applyStyle(styleMode);

      // Draw interaction lines if available
      if (interactions) {
        drawInteractions(interactions);
      }

      setStatus('ready');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to build scene');
      setStatus('error');
    }
  }, [pdbId, ligandPdb, interactions, styleMode]);

  const applyStyle = useCallback((mode: StyleMode) => {
    const plugin = pluginRef.current?.plugin;
    if (!plugin) return;

    try {
      // Clear existing representations
      plugin.clear();

      // Rebuild with style
      const build = plugin.build();
      if (build && typeof build === 'object' && 'to' in build) {
        const b = build as Record<string, unknown>;
        if (typeof b.to === 'function') {
          (b.to as (selector: unknown) => unknown)({});
        }
      }

      plugin.canvas3d?.requestDraw();
    } catch {
      // Style application is best-effort
    }
  }, []);

  const drawInteractions = useCallback((inter: DockingInteraction) => {
    const plugin = pluginRef.current?.plugin;
    if (!plugin) return;

    try {
      // Clear previous primitives
      if (plugin.primitives?.clear) {
        plugin.primitives.clear();
      }

      const primitives: unknown[] = [];

      // H-bonds as blue dashed cylinders
      for (const hb of inter.hbonds || []) {
        if (hb.ligand_coords && hb.protein_coords) {
          primitives.push({
            kind: 'cylinder',
            start: { x: hb.ligand_coords[0], y: hb.ligand_coords[1], z: hb.ligand_coords[2] },
            end: { x: hb.protein_coords[0], y: hb.protein_coords[1], z: hb.protein_coords[2] },
            color: 0x4488ff,
            radius: 0.15,
            dashLength: 0.3,
            gapLength: 0.2,
          });
        }
      }

      // Hydrophobic as orange dashed cylinders
      for (const hp of inter.hydrophobic || []) {
        if (hp.ligand_coords && hp.protein_coords) {
          primitives.push({
            kind: 'cylinder',
            start: { x: hp.ligand_coords[0], y: hp.ligand_coords[1], z: hp.ligand_coords[2] },
            end: { x: hp.protein_coords[0], y: hp.protein_coords[1], z: hp.protein_coords[2] },
            color: 0xff8844,
            radius: 0.12,
            dashLength: 0.25,
            gapLength: 0.2,
          });
        }
      }

      // Pi-stacking as magenta cylinders (centroid to centroid)
      for (const ps of inter.pi_stacking || []) {
        if (ps.ring_centroid && ps.ligand_centroid) {
          primitives.push({
            kind: 'cylinder',
            start: { x: ps.ring_centroid[0], y: ps.ring_centroid[1], z: ps.ring_centroid[2] },
            end: { x: ps.ligand_centroid[0], y: ps.ligand_centroid[1], z: ps.ligand_centroid[2] },
            color: 0xff44ff,
            radius: 0.18,
            dashLength: 0.35,
            gapLength: 0.15,
          });
        }
      }

      // Salt bridges as cyan cylinders
      for (const sb of inter.salt_bridges || []) {
        if (sb.ligand_coords && sb.protein_coords) {
          primitives.push({
            kind: 'cylinder',
            start: { x: sb.ligand_coords[0], y: sb.ligand_coords[1], z: sb.ligand_coords[2] },
            end: { x: sb.protein_coords[0], y: sb.protein_coords[1], z: sb.protein_coords[2] },
            color: 0x00cccc,
            radius: 0.2,
            dashLength: 0.4,
            gapLength: 0.15,
          });
        }
      }

      if (primitives.length > 0 && plugin.primitives?.add) {
        plugin.primitives.add(primitives);
      }

      plugin.canvas3d?.requestDraw();
    } catch {
      // Interaction drawing is best-effort — pdbe-molstar may not expose primitives API
    }
  }, []);

  useEffect(() => {
    if (!pdbId || !ligandPdb) {
      setStatus('error');
      setError('Missing structure data');
      return;
    }

    let cancelled = false;

    const init = async () => {
      setStatus('loading');
      setError(null);

      try {
        // Wait for PDBeMolstarPlugin to be available
        let attempts = 0;
        while (!window.PDBeMolstarPlugin && attempts < 50) {
          await new Promise(r => setTimeout(r, 200));
          attempts++;
        }

        if (!window.PDBeMolstarPlugin || !containerRef.current) {
          throw new Error('Molstar failed to load');
        }

        if (cancelled) return;

        const plugin = new window.PDBeMolstarPlugin();
        pluginRef.current = plugin;

        await plugin.render(containerRef.current, {
          moleculeId: pdbId.toLowerCase(),
          backgroundColor,
          hideControls: true,
          hideCanvasControls: false,
          sequencePanel: false,
          ligandView: { hide: true },
          crystallographicInfo: false,
          secondaryStructure: { display: true },
        });

        if (cancelled) return;

        await buildScene();
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to initialize');
          setStatus('error');
        }
      }
    };

    init();

    return () => { cancelled = true; };
  }, [pdbId, ligandPdb, backgroundColor, buildScene]);

  // Redraw interactions when they change
  useEffect(() => {
    if (status === 'ready' && interactions) {
      drawInteractions(interactions);
    }
  }, [interactions, status, drawInteractions]);

  // Spin control
  useEffect(() => {
    const plugin = pluginRef.current?.plugin;
    if (!plugin?.canvas3d?.camera) return;
    plugin.canvas3d.camera.spin(spinning);
  }, [spinning, status]);

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
