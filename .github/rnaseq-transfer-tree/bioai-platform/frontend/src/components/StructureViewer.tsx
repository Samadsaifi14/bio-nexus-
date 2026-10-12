'use client';

import { useEffect, useRef, useState } from 'react';
import { useTheme } from '@/contexts/theme';
import { ensurePdbeMolstar } from '@/lib/pdbeMolstar';

type Props = {
  pdbId: string;
  height?: string;
};

export default function StructureViewer({ pdbId, height = 'h-96' }: Props) {
  const { theme } = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const viewerId = `pdbe-${pdbId.toLowerCase()}`;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let cancelled = false;
    setStatus('loading');
    container.innerHTML = '';

    const mountViewer = async () => {
      try {
        await ensurePdbeMolstar();
        if (cancelled || !containerRef.current) return;

        const el = document.createElement('pdbe-molstar');
        el.setAttribute('molecule-id', pdbId.toLowerCase());
        el.setAttribute('hide-controls', '');
        el.setAttribute('loading-overlay', '');
        el.setAttribute('background-color', theme === 'light' ? '#FFFFFF' : '#06060B');
        el.id = viewerId;
        container.appendChild(el);
        setStatus('ready');
      } catch {
        if (!cancelled) setStatus('error');
      }
    };

    void mountViewer();

    return () => {
      cancelled = true;
      container.innerHTML = '';
    };
  }, [pdbId, viewerId, theme]);

  return (
    <div className="relative">
      <div ref={containerRef} className={`w-full ${height} rounded-xl overflow-hidden border-0`} />
      {status === 'loading' && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-xs text-text-muted">
          Loading structure viewer…
        </div>
      )}
      {status === 'error' && (
        <div className="absolute inset-0 flex items-center justify-center px-4 text-center text-xs text-error">
          The 3D viewer could not be loaded. The underlying structure data remains available.
        </div>
      )}
    </div>
  );
}
