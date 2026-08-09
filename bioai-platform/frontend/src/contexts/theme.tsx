'use client';

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { THEME_STORAGE_KEY, type Theme } from '@/lib/theme';

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: 'dark',
  setTheme: () => {},
  toggleTheme: () => {},
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>('dark');

  useEffect(() => {
    const current = document.documentElement.getAttribute('data-theme');
    if (current === 'light' || current === 'dark') setThemeState(current);
  }, []);

  const applyTransition = () => {
    const el = document.documentElement;
    el.classList.add('theme-switching');
    window.setTimeout(() => el.classList.remove('theme-switching'), 260);
  };

  const setTheme = useCallback((next: Theme) => {
    applyTransition();
    setThemeState(next);
    document.documentElement.setAttribute('data-theme', next);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {}
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(theme === 'light' ? 'dark' : 'light');
  }, [theme, setTheme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
