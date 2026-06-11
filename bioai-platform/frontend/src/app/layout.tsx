import type { Metadata } from 'next';
import './globals.css';
import { Toaster } from 'react-hot-toast';
import { Providers } from './providers';

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
    <html lang="en">
      <body className="font-sans antialiased">
        <Providers>
          {children}
        </Providers>
        <Toaster position="bottom-right" />
      </body>
    </html>
  );
}