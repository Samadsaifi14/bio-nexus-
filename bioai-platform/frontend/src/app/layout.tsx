import type { Metadata } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import Script from 'next/script';
import { MotionConfig } from 'framer-motion';
import './globals.css';
import { Toaster } from 'react-hot-toast';
import { Providers } from './providers';
import { themeInitScript } from '@/lib/theme';

export const metadata: Metadata = {
  title: 'Bio Nexus — One interface for every bioinformatics tool',
  description: 'Protein sequence analysis, BLAST, UniProt, AlphaFold, docking — all in one place. Built for researchers who aren\'t bioinformaticians.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <head>
        <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/pdbe-molstar@3.12.0/build/pdbe-molstar.css" />
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="font-sans antialiased">
        <Providers>
          <MotionConfig reducedMotion="user">
            {children}
          </MotionConfig>
        </Providers>
        <Toaster position="bottom-right" />
        <Script src="https://cdn.jsdelivr.net/npm/pdbe-molstar@3.12.0/build/pdbe-molstar-component.js" strategy="lazyOnload" />
      </body>
    </html>
  );
}
