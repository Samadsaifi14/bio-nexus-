import type { AssembledContext } from '@/types/pipeline';

export interface ShareDetails {
  queryLabel?: string;
  topHit?: string;
  hitCount?: number;
  length?: number;
  sequenceType?: string;
}

export function buildShareUrl(tokenOrUrl: string): string {
  if (tokenOrUrl.startsWith('http')) return tokenOrUrl;
  return `${window.location.origin}/shared/${tokenOrUrl}`;
}

/** Extracts a short human-readable summary from a results context. */
export function buildShareDetails(context?: AssembledContext | null): ShareDetails | undefined {
  if (!context) return undefined;
  const details: ShareDetails = {};
  const query = context.query;
  const blast = context.blast;

  if (blast) {
    const top = blast.top_hit;
    if (top?.accession) {
      const pct = typeof top.identity_pct === 'number' ? `${Math.round(top.identity_pct)}% identity` : '';
      const label = (top.description || '').split(',')[0]?.split('[')[0]?.trim() || '';
      details.topHit = [top.accession, label, pct].filter(Boolean).join(' · ');
    }
    if (typeof blast.count === 'number') details.hitCount = blast.count;
  }

  if (query?.accession) {
    details.queryLabel = query.accession;
  } else if (query?.sequence) {
    details.queryLabel = query.sequence.length > 32 ? `${query.sequence.slice(0, 32)}…` : query.sequence;
  }

  details.length = query?.length ?? context.length;
  details.sequenceType = query?.sequence_type ?? (context.sequence ? undefined : 'protein');
  return details;
}

export function buildShareMessage(shareLink: string, details?: ShareDetails): string {
  const lines: string[] = ['My Synteny analysis result is ready.'];
  if (details?.topHit) lines.push(`Best match: ${details.topHit}`);
  if (typeof details?.hitCount === 'number') {
    lines.push(`${details.hitCount} similar sequence${details.hitCount === 1 ? '' : 's'} found.`);
  }
  if (details?.queryLabel) lines.push(`Query: ${details.queryLabel}`);
  if (typeof details?.length === 'number') {
    lines.push(`Length: ${details.length} ${details.sequenceType === 'dna' ? 'bp' : 'aa'}`);
  }
  lines.push('', shareLink, '', 'Powered by Synteny — sequence analysis, docking, and AI interpretation.');
  return lines.join('\n');
}

export interface SharePlatform {
  id: string;
  label: string;
  /** Returns the share target URL (popup link or mailto). */
  buildUrl: (url: string, message: string) => string;
}

/** Share targets shown alongside the copyable link in the share dialog. */
export const SHARE_PLATFORMS: SharePlatform[] = [
  {
    id: 'x',
    label: 'X',
    buildUrl: (url, message) => `https://twitter.com/intent/tweet?text=${encodeURIComponent(message)}&url=${encodeURIComponent(url)}`,
  },
  {
    id: 'facebook',
    label: 'Facebook',
    buildUrl: (url) => `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`,
  },
  {
    id: 'linkedin',
    label: 'LinkedIn',
    buildUrl: (url) => `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`,
  },
  {
    id: 'whatsapp',
    label: 'WhatsApp',
    buildUrl: (url, message) => `https://wa.me/?text=${encodeURIComponent(`${message}\n${url}`)}`,
  },
  {
    id: 'telegram',
    label: 'Telegram',
    buildUrl: (url, message) => `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(message)}`,
  },
  {
    id: 'reddit',
    label: 'Reddit',
    buildUrl: (url) => `https://www.reddit.com/submit?url=${encodeURIComponent(url)}`,
  },
  {
    id: 'email',
    label: 'Email',
    buildUrl: (url, message) =>
      `mailto:?subject=${encodeURIComponent('Synteny — Analysis Result')}&body=${encodeURIComponent(`${message}\n\n${url}`)}`,
  },
];

/** Opens a share target in a popup/email client for a platform option. */
export function openSharePlatform(platform: SharePlatform, url: string, message: string): void {
  const target = platform.buildUrl(url, message);
  if (platform.id === 'email') {
    window.location.href = target;
    return;
  }
  window.open(target, '_blank', 'noopener,noreferrer,width=640,height=560');
}
