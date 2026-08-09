export type Theme = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'bio-nexus-theme';

export function resolveStoredTheme(): Theme | null {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {}
  return null;
}

export function resolveSystemTheme(): Theme {
  try {
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  } catch {}
  return 'dark';
}

/**
 * Inlined into <head> so it runs synchronously before first paint and
 * prevents a flash-of-wrong-theme. Explicit user choice wins; otherwise
 * falls back to the OS preference. Never touches the stored choice.
 */
export const themeInitScript = `(function(){try{var s=localStorage.getItem('${THEME_STORAGE_KEY}');var t=(s==='light'||s==='dark')?s:(window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark');document.documentElement.setAttribute('data-theme',t);}catch(e){document.documentElement.setAttribute('data-theme','dark');}})();`;
