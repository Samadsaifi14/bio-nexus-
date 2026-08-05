export function buildShareUrl(tokenOrUrl: string): string {
  if (tokenOrUrl.startsWith('http')) return tokenOrUrl;
  return `${window.location.origin}/shared/${tokenOrUrl}`;
}

export function buildShareMessage(shareLink: string): string {
  return `Check out my bioinformatics analysis result on BioNexus:\n${shareLink}\n\nPowered by BioNexus — sequence analysis, docking, and beyond.`;
}

/**
 * Shares a result using the native Web Share API when available,
 * otherwise copies a pre-filled share message to the clipboard.
 * Returns 'shared' when the native share dialog was used (not cancelled).
 */
export async function shareResult(tokenOrUrl: string): Promise<'shared' | 'copied'> {
  const shareLink = buildShareUrl(tokenOrUrl);
  const message = buildShareMessage(shareLink);

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
