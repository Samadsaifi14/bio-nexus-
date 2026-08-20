'use client';

import { useEffect, useRef, useState } from 'react';

interface IGVBrowserProps {
  referenceUrl: string;
  bamUrl?: string;
  baiUrl?: string;
  samUrl?: string;
  vcfUrl?: string;
  locus?: string;
  className?: string;
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

        const igv = (await import('igv')).default;
        if (cancelled || !containerRef.current) return;

        // Destroy previous instance
        if (browserRef.current) {
          try { browserRef.current.destroy(); } catch {}
          browserRef.current = null;
        }

        // Clear the container completely
        containerRef.current.innerHTML = '';

        const tracks: any[] = [];

        // Alignment track: prefer BAM, fallback to SAM
        const alignmentUrl = bamUrl || samUrl;
        if (alignmentUrl) {
          const isBam = !!bamUrl;
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

        const browser = await igv.createBrowser(containerRef.current, {
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

    // Small delay to ensure DOM is ready
    const timer = setTimeout(init, 100);

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
      <div ref={containerRef} style={{ width: '100%', minHeight: '400px' }} />
      {status === 'loading' && (
        <div className="flex items-center justify-center py-12 bg-surface-1 rounded-xl">
          <div className="w-5 h-5 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
          <span className="ml-3 text-sm text-text-muted">Loading genome browser...</span>
        </div>
      )}
      {status === 'error' && (
        <div className="p-4 bg-error/5 border border-error/20 rounded-xl">
          <p className="text-sm text-error font-medium">Genome browser failed to load</p>
          <p className="text-xs text-error/70 mt-1 font-mono">{errorMsg}</p>
        </div>
      )}
    </div>
  );
}
