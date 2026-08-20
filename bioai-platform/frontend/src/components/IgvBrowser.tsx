'use client';

import { useEffect, useRef } from 'react';

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

  useEffect(() => {
    if (!containerRef.current || !referenceUrl) return;
    let cancelled = false;

    async function init() {
      const igv = (await import('igv')).default;
      if (cancelled || !containerRef.current) return;

      if (browserRef.current) {
        try { browserRef.current.destroy(); } catch {}
      }

      const tracks: any[] = [];

      // Use BAM if available, else SAM
      const alignmentUrl = bamUrl || samUrl;
      if (alignmentUrl) {
        const isBam = alignmentUrl.endsWith('.bam') || bamUrl;
        tracks.push({
          name: 'Aligned Reads',
          url: alignmentUrl,
          indexURL: isBam ? (baiUrl || alignmentUrl + '.bai') : undefined,
          format: isBam ? 'bam' : 'sam',
          type: 'alignment',
          color: '#3b82f6',
          height: 200,
          indexed: !!isBam,
          displayMode: 'expanded',
        });
      }

      if (vcfUrl) {
        tracks.push({
          name: 'Variants',
          url: vcfUrl,
          format: 'vcf',
          type: 'variant',
          color: '#f59e0b',
          height: 120,
          displayMode: 'expanded',
        });
      }

      try {
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
        } else {
          try { browser.destroy(); } catch {}
        }
      } catch (err) {
        console.error('Failed to create IGV browser:', err);
      }
    }

    init();

    return () => {
      cancelled = true;
      if (browserRef.current) {
        try { browserRef.current.destroy(); } catch {}
        browserRef.current = null;
      }
    };
  }, [referenceUrl, bamUrl, baiUrl, samUrl, vcfUrl, locus]);

  return (
    <div className={className}>
      <div ref={containerRef} style={{ width: '100%', height: '500px', minHeight: '400px' }} />
    </div>
  );
}
