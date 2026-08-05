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
  const lines: string[] = ['My BioNexus analysis result is ready.'];
  if (details?.topHit) lines.push(`Best match: ${details.topHit}`);
  if (typeof details?.hitCount === 'number') {
    lines.push(`${details.hitCount} similar sequence${details.hitCount === 1 ? '' : 's'} found.`);
  }
  if (details?.queryLabel) lines.push(`Query: ${details.queryLabel}`);
  if (typeof details?.length === 'number') {
    lines.push(`Length: ${details.length} ${details.sequenceType === 'dna' ? 'bp' : 'aa'}`);
  }
  lines.push('', shareLink, '', 'Powered by BioNexus — sequence analysis, docking, and AI interpretation.');
  return lines.join('\n');
}

/**
 * Shares a result using the native Web Share API when available,
 * otherwise copies a pre-filled share message to the clipboard.
 * Returns 'shared' when the native share dialog was used (not cancelled).
 */
export async function shareResult(tokenOrUrl: string, details?: ShareDetails): Promise<'shared' | 'copied'> {
  const shareLink = buildShareUrl(tokenOrUrl);
  const message = buildShareMessage(shareLink, details);

  if (typeof navigator !== 'undefined' && typeof navigator.share === 'function') {
    try {
      await navigator.share({ title: 'BioNexus — Analysis Result', text: message, url: shareLink });
      return 'shared';
    } catch {
      // User dismissed the share sheet — fall through to clipboard copy.
    }
  }

  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(message);
    return 'copied';
  }

  const textarea = document.createElement('textarea');
  textarea.value = message;
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand('copy');
  document.body.removeChild(textarea);
  return 'copied';
}
