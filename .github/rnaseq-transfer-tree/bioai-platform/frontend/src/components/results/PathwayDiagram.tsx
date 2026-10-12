'use client';

import { useEffect, useRef, useState } from 'react';
import { CircleNotch as LoaderCircle, DownloadSimple as Download } from '@phosphor-icons/react';
import { downloadText } from '@/lib/export-utils';

interface Props {
  stId: string;
  geneName?: string;
  height?: number;
}

declare global {
  interface Window {
    Reactome?: {
      Diagram: {
        create: (params: {
          placeHolder: string;
          width?: number;
          height?: number;
          proxyPrefix?: string;
        }) => {
          loadDiagram: (stId: string) => void;
          flagItems: (term: string) => void;
          selectItem: (stId: string) => void;
          resetHighlight: () => void;
          resetSelection: () => void;
          onDiagramLoaded: (cb: (stId: string) => void) => void;
          onObjectSelected: (cb: (obj: { stId: string; displayName: string }) => void) => void;
          onObjectHovered: (cb: (obj: { stId: string; displayName: string }) => void) => void;
        };
      };
    };
    onReactomeDiagramReady?: () => void;
  }
}

const ISOLATION_CSS = (id: string) => `
#${id} {
  color-scheme: light;
  background: #fff;
  color: #1a1a2e;
}
#${id} * {
  color: revert !important;
  background-color: revert !important;
  background-image: revert !important;
  font-family: revert !important;
  font-size: revert !important;
  font-weight: revert !important;
  line-height: revert !important;
  text-align: revert !important;
}
`;

export default function PathwayDiagram({ stId, geneName, height = 400 }: Props) {
  const containerId = useRef(`diagram-${stId}-${Math.random().toString(36).slice(2, 8)}`).current;
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  type DiagramInstance = ReturnType<NonNullable<typeof window.Reactome>['Diagram']['create']>;
  const diagramRef = useRef<DiagramInstance | null>(null);
  const initCalled = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const exportSvg = () => {
    const svg = containerRef.current?.querySelector('svg');
    if (!svg) return;
    downloadText(new XMLSerializer().serializeToString(svg), `${stId}_pathway.svg`);
  };

  const exportPng = () => {
    const svg = containerRef.current?.querySelector('svg');
    if (!svg) return;
    const svgStr = new XMLSerializer().serializeToString(svg);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;
    const img = new window.Image();
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
      const a = document.createElement('a');
      a.download = `${stId}_pathway.png`;
      a.href = canvas.toDataURL('image/png');
      a.click();
    };
    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgStr)));
  };

  useEffect(() => {
    const style = document.createElement('style');
    style.textContent = ISOLATION_CSS(containerId);
    document.head.appendChild(style);

    if (initCalled.current) return;
    initCalled.current = true;

    if (window.Reactome?.Diagram) {
      initDiagram();
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://reactome.org/DiagramJs/diagram/diagram.nocache.js';
    script.async = true;
    script.onerror = () => setError('Failed to load Reactome DiagramJs');
    document.head.appendChild(script);

    const origReady = window.onReactomeDiagramReady;
    window.onReactomeDiagramReady = () => {
      origReady?.();
      initDiagram();
    };

    return () => {
      style.remove();
      if (diagramRef.current) {
        diagramRef.current.resetHighlight();
        diagramRef.current.resetSelection();
      }
    };
  }, []);

  function initDiagram() {
    if (!window.Reactome?.Diagram) {
      const check = setInterval(() => {
        if (window.Reactome?.Diagram) {
          clearInterval(check);
          createDiagram();
        }
      }, 200);
      setTimeout(() => clearInterval(check), 10000);
      return;
    }
    createDiagram();
  }

  function createDiagram() {
    try {
      const diagram = window.Reactome!.Diagram.create({
        placeHolder: containerId,
        width: 950,
        height,
      });
      diagramRef.current = diagram;

      diagram.onDiagramLoaded(() => {
        setLoaded(true);
        if (geneName) {
          diagram.flagItems(geneName);
        }
      });

      diagram.loadDiagram(stId);
    } catch {
      setError('Failed to initialize diagram viewer');
    }
  }

  return (
    <div className="relative">
      {loaded && (
        <div className="flex items-center justify-end gap-2 mb-2">
          <button
            onClick={exportSvg}
            className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors flex items-center gap-1.5"
          >
            <Download className="w-3.5 h-3.5" /> SVG
          </button>
          <button
            onClick={exportPng}
            className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors flex items-center gap-1.5"
          >
            <Download className="w-3.5 h-3.5" /> PNG
          </button>
        </div>
      )}
      <div ref={containerRef} id={containerId} className="w-full rounded-xl overflow-hidden" style={{ minHeight: height, opacity: loaded ? 1 : 0 }} />
      {!loaded && !error && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface-1/50 rounded-xl">
          <LoaderCircle className="w-6 h-6 animate-spin text-accent-cyan" />
        </div>
      )}
      {error && (
        <p className="text-sm text-error">{error}</p>
      )}
    </div>
  );
}
