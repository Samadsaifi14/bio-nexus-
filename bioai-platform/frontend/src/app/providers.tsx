'use client';

import { type ReactNode } from 'react';
import { AuthProvider } from '@/contexts/auth';
import { ThemeProvider } from '@/contexts/theme';

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <AuthProvider>{children}</AuthProvider>
    </ThemeProvider>
  );
}
