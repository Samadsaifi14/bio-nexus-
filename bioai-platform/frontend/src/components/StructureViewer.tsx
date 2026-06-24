'use client';

import { useEffect, useRef } from 'react';

type Props = {
  pdbId: string;
  height?: string;
};

export default function StructureViewer({ pdbId, height = 'h-96' }: Props) {
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
    el.setAttribute('background-color', '#04040A');
    el.id = viewerId;
    container.appendChild(el);

    return () => {
      container.innerHTML = '';
    };
  }, [pdbId, viewerId]);

  return (
    <div ref={containerRef} className={`w-full ${height} rounded-xl overflow-hidden border-0`} />
  );
}
