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
  return 'light';
}

/** Keep the Field Notes palette stable before the first paint. */
export const themeInitScript = `document.documentElement.setAttribute('data-theme','light');`;
