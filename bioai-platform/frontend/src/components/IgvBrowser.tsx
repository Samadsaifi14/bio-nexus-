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

async function fetchBlobUrl(url: string, label: string): Promise<string> {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Failed to fetch ${label}: HTTP ${resp.status}`);
  const blob = await resp.blob();
  if (blob.size === 0) throw new Error(`${label} is empty (0 bytes)`);
  return URL.createObjectURL(blob);
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
  const blobUrlsRef = useRef<string[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (!containerRef.current || !referenceUrl) return;
    let cancelled = false;

    async function init() {
      try {
        setStatus('loading');
        setErrorMsg('');

        // Clean up previous blob URLs
        for (const u of blobUrlsRef.current) URL.revokeObjectURL(u);
        blobUrlsRef.current = [];

        // Load igv.js from CDN
        await loadScript(IGV_CDN_URL);
        if (cancelled || !containerRef.current) return;
        if (!window.igv) throw new Error('igv.js failed to load from CDN');

        // Destroy previous instance
        if (browserRef.current) {
          try { browserRef.current.destroy(); } catch {}
          browserRef.current = null;
        }
        containerRef.current.innerHTML = '';

        const tracks: any[] = [];

        // Fetch reference FASTA as Blob URL
        let refBlobUrl: string;
        try {
          refBlobUrl = await fetchBlobUrl(referenceUrl, 'reference FASTA');
          blobUrlsRef.current.push(refBlobUrl);
        } catch (e: any) {
          throw new Error(`Reference genome fetch failed: ${e.message}`);
        }

        // Fetch BAM + BAI as Blob URLs (igv.js ONLY supports BAM for alignment tracks)
        let hasAlignment = false;
        if (bamUrl && baiUrl) {
          try {
            const bamBlob = await fetchBlobUrl(bamUrl, 'BAM');
            const baiBlob = await fetchBlobUrl(baiUrl, 'BAI');
            blobUrlsRef.current.push(bamBlob, baiBlob);

            tracks.push({
              name: 'Aligned Reads',
              url: bamBlob,
              type: 'alignment',
              format: 'bam',
              indexURL: baiBlob,
              color: '#3b82f6',
              height: 200,
              displayMode: 'expanded',
              indexed: true,
            });
            hasAlignment = true;
          } catch (e: any) {
            console.error('[IGV] BAM/BAI load failed:', e.message);
          }
        }

        // Fetch VCF as Blob URL
        if (vcfUrl) {
          try {
            const vcfBlob = await fetchBlobUrl(vcfUrl, 'VCF');
            blobUrlsRef.current.push(vcfBlob);

            tracks.push({
              name: 'Variants',
              url: vcfBlob,
              format: 'vcf',
              type: 'variant',
              color: '#f59e0b',
              height: 120,
              displayMode: 'expanded',
              indexed: false,
            });
          } catch (e: any) {
            console.error('[IGV] VCF load failed:', e.message);
          }
        }

        const browser = await window.igv.createBrowser(containerRef.current, {
          reference: {
            fastaURL: refBlobUrl,
            indexed: false,
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
        console.error('[IGV] Error:', err);
        if (!cancelled) {
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
      for (const u of blobUrlsRef.current) URL.revokeObjectURL(u);
      blobUrlsRef.current = [];
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
