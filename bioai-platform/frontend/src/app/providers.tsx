'use client';

import { type ReactNode } from 'react';
import { AuthProvider } from '@/contexts/auth';
import { ThemeProvider } from '@/contexts/theme';
import SmoothScrollProvider from '@/components/SmoothScrollProvider';

export function Providers({ children }: { children: ReactNode }) {
  return (
    <SmoothScrollProvider>
      <ThemeProvider>
        <AuthProvider>{children}</AuthProvider>
      </ThemeProvider>
    </SmoothScrollProvider>
  );
}
