'use client';

import { useEffect, useRef, useState } from 'react';
import { LoaderCircle } from 'lucide-react';

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

export default function PathwayDiagram({ stId, geneName, height = 400 }: Props) {
  const containerId = useRef(`diagram-${stId}-${Math.random().toString(36).slice(2, 8)}`).current;
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  type DiagramInstance = ReturnType<NonNullable<typeof window.Reactome>['Diagram']['create']>;
  const diagramRef = useRef<DiagramInstance | null>(null);
  const initCalled = useRef(false);

  useEffect(() => {
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
      <div id={containerId} className="w-full rounded-xl overflow-hidden" style={{ minHeight: height, opacity: loaded ? 1 : 0 }} />
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
