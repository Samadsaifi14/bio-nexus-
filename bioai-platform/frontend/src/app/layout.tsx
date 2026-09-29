import type { Metadata } from 'next';
import Script from 'next/script';
import { MotionConfig } from 'framer-motion';
import './globals.css';
import './scientific-ui.css';
import './scientific-data-surface.css';
import './experience.css';
import { Toaster } from 'react-hot-toast';
import { Providers } from './providers';
import { themeInitScript } from '@/lib/theme';
import { JsonLd } from '@/components/seo/JsonLd';
import { ORG_ID, SITE_NAME, SITE_URL, WEBSITE_ID } from '@/lib/seo';

export const metadata: Metadata = {
  title: 'BioNexus — Bioinformatics research workspace',
  description: 'Explore sequencing, sequence biology and structural methods with quality checks, results and scientific context in one workspace.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/pdbe-molstar@3.12.0/build/pdbe-molstar.css" />
        <Script
          src="https://cdn.jsdelivr.net/npm/pdbe-molstar@3.12.0/build/pdbe-molstar-component.js"
          strategy="beforeInteractive"
        />
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
                  'BioNexus brings sequencing, sequence analysis and structural methods into a research workspace with scientific result views.',
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
      </body>
    </html>
  );
}
