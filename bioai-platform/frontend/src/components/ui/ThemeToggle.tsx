'use client';

import { Moon, Sun } from '@phosphor-icons/react';
import { useTheme } from '@/contexts/theme';

export function ThemeToggle({ className = '' }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <button
      onClick={toggleTheme}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      className={`flex items-center justify-center w-9 h-9 rounded-full border border-glass-border bg-surface-1/70 text-text-secondary hover:text-accent-cyan hover:border-accent-cyan/40 transition-colors cursor-pointer ${className}`}
    >
      {isDark ? <Sun size={16} weight="bold" /> : <Moon size={16} weight="bold" />}
    </button>
  );
}
