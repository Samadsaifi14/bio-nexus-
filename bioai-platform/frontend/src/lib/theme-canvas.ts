/**
 * Resolve a theme-driven CSS variable to a concrete color string at runtime.
 * Used by canvas/export code (fillStyle, SVG serialization, 3D viewers) where a
 * bare `var(--x)` cannot be passed to a non-CSS API. Safe for SSR.
 */

export function cssColor(name: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (!value) return fallback;
  // Triplet tokens ("11 12 20") -> rgb(11 12 20); full colors pass through.
  if (/^\d[\d\s]*$/.test(value)) return `rgb(${value})`;
  return value;
}

/** Resolved scene/canvas background (driven by --viewer-bg). */
export function viewerBg(fallback = '#0B0C14'): string {
  return cssColor('--viewer-bg', fallback);
}
