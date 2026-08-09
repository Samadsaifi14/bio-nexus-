'use client';

import { useEffect, useRef } from 'react';
import { useTheme } from '@/contexts/theme';

type Props = {
  pdbId: string;
  height?: string;
};

export default function StructureViewer({ pdbId, height = 'h-96' }: Props) {
  const { theme } = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerId = `pdbe-${pdbId.toLowerCase()}`;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.innerHTML = '';

    const el = document.createElement('pdbe-molstar');
    el.setAttribute('molecule-id', pdbId.toLowerCase());
    el.setAttribute('hide-controls', '');
    el.setAttribute('loading-overlay', '');
    el.setAttribute('background-color', theme === 'light' ? '#FFFFFF' : '#06060B');
    el.id = viewerId;
    container.appendChild(el);

    return () => {
      container.innerHTML = '';
    };
  }, [pdbId, viewerId, theme]);

  return (
    <div ref={containerRef} className={`w-full ${height} rounded-xl overflow-hidden border-0`} />
  );
}
