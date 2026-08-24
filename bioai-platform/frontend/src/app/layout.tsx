import type { Metadata } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import Script from 'next/script';
import { MotionConfig } from 'framer-motion';
import './globals.css';
import { Toaster } from 'react-hot-toast';
import { Providers } from './providers';
import { themeInitScript } from '@/lib/theme';
import { JsonLd } from '@/components/seo/JsonLd';
import { ORG_ID, SITE_NAME, SITE_URL, WEBSITE_ID } from '@/lib/seo';

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
        <JsonLd
          data={{
            '@context': 'https://schema.org',
            '@graph': [
              {
                '@type': 'Organization',
                '@id': ORG_ID,
                name: SITE_NAME,
                url: `${SITE_URL}/`,
                description:
                  'Bio Nexus unifies BLAST, UniProt, AlphaFold, molecular docking and AI interpretation into a single bioinformatics research interface.',
                sameAs: ['https://github.com/Samadsaifi14/bio-nexus-'],
                foundingLocation: {
                  '@type': 'Place',
                  name: 'Jamia Millia Islamia, New Delhi',
                },
              },
              {
                '@type': 'WebSite',
                '@id': WEBSITE_ID,
                url: `${SITE_URL}/`,
                name: SITE_NAME,
                publisher: { '@id': ORG_ID },
                inLanguage: 'en-US',
              },
            ],
          }}
        />
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
