'use client';

import { useEffect, useRef, useState } from 'react';

declare global {
  interface Window {
    igv: any;
  }
}

const IGV_CDN_URL = 'https://cdn.jsdelivr.net/npm/igv@3.8.5/dist/igv.min.js';

interface IGVBrowserProps {
  referenceUrl: string;
  bamUrl?: string;
  baiUrl?: string;
  samUrl?: string;
  vcfUrl?: string;
  locus?: string;
  className?: string;
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve();
      return;
    }
    const script = document.createElement('script');
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

export default function IGVBrowser({
  referenceUrl,
  bamUrl,
  baiUrl,
  samUrl,
  vcfUrl,
  locus,
  className = '',
}: IGVBrowserProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const browserRef = useRef<any>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (!containerRef.current || !referenceUrl) return;
    let cancelled = false;

    async function init() {
      try {
        setStatus('loading');
        setErrorMsg('');

        // Load igv.js from CDN
        await loadScript(IGV_CDN_URL);

        if (cancelled || !containerRef.current) return;
        if (!window.igv) {
          throw new Error('igv.js failed to load from CDN');
        }

        // Destroy previous instance
        if (browserRef.current) {
          try { browserRef.current.destroy(); } catch {}
          browserRef.current = null;
        }

        containerRef.current.innerHTML = '';

        const tracks: any[] = [];

        // Alignment track: prefer SAM (text, zero format risk) over BAM
        const alignmentUrl = samUrl || bamUrl;
        if (alignmentUrl) {
          const isBam = !!bamUrl && alignmentUrl === bamUrl;
          const track: any = {
            name: 'Aligned Reads',
            url: alignmentUrl,
            type: 'alignment',
            color: '#3b82f6',
            height: 200,
            displayMode: 'expanded',
          };

          if (isBam) {
            track.format = 'bam';
            track.indexURL = baiUrl || alignmentUrl + '.bai';
            track.indexed = true;
          } else {
            track.format = 'sam';
            track.indexed = false;
          }

          tracks.push(track);
        }

        // Variant track
        if (vcfUrl) {
          tracks.push({
            name: 'Variants',
            url: vcfUrl,
            format: 'vcf',
            type: 'variant',
            color: '#f59e0b',
            height: 120,
            displayMode: 'expanded',
            indexed: false,
          });
        }

        const browser = await window.igv.createBrowser(containerRef.current, {
          reference: {
            fastaURL: referenceUrl,
          },
          tracks,
          locus: locus || '1',
          showNavigation: true,
          showRuler: true,
        });

        if (!cancelled) {
          browserRef.current = browser;
          setStatus('ready');
        } else {
          try { browser.destroy(); } catch {}
        }
      } catch (err: any) {
        if (!cancelled) {
          console.error('IGV init error:', err);
          setStatus('error');
          setErrorMsg(err?.message || 'Failed to initialize genome browser');
        }
      }
    }

    const timer = setTimeout(init, 200);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      if (browserRef.current) {
        try { browserRef.current.destroy(); } catch {}
        browserRef.current = null;
      }
    };
  }, [referenceUrl, bamUrl, baiUrl, samUrl, vcfUrl, locus]);

  return (
    <div className={className}>
      {status === 'loading' && (
        <div className="flex items-center justify-center py-12 bg-surface-1 rounded-xl">
          <div className="w-5 h-5 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
          <span className="ml-3 text-sm text-text-muted">Loading genome browser...</span>
        </div>
      )}
      <div
        ref={containerRef}
        style={{
          width: '100%',
          minHeight: status === 'ready' ? '500px' : '0px',
          display: status === 'loading' ? 'none' : 'block',
        }}
      />
      {status === 'error' && (
        <div className="p-4 bg-error/5 border border-error/20 rounded-xl mt-2">
          <p className="text-sm text-error font-medium">Genome browser failed to load</p>
          <p className="text-xs text-error/70 mt-1 font-mono">{errorMsg}</p>
        </div>
      )}
    </div>
  );
}
