'use client';

import { Sun, Moon } from 'lucide-react';
import { useTheme } from '@/contexts/theme';

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { theme, toggle } = useTheme();

  if (compact) {
    return (
      <button
        onClick={toggle}
        className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition"
        title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {theme === 'dark' ? <Sun className="w-4 h-4 text-gray-400" /> : <Moon className="w-4 h-4 text-gray-500" />}
      </button>
    );
  }

  return (
    <button
      onClick={toggle}
      className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800"
    >
      {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
      {theme === 'dark' ? 'Light mode' : 'Dark mode'}
    </button>
  );
}
