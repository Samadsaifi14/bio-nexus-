import type { Metadata } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import { MotionConfig } from 'framer-motion';
import './globals.css';
import './scientific-ui.css';
import './scientific-data-surface.css';
import { Toaster } from 'react-hot-toast';
import { Providers } from './providers';
import { themeInitScript } from '@/lib/theme';
import { JsonLd } from '@/components/seo/JsonLd';
import { ORG_ID, SITE_NAME, SITE_URL, WEBSITE_ID } from '@/lib/seo';

const description =
  'Provenance-aware bioinformatics workspace for sequence analysis, structures, docking, NGS/RNA-seq, scientific figures and evidence-backed interpretation.';

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  applicationName: SITE_NAME,
  title: {
    default: 'Bio Nexus — Bioinformatics analysis with traceable scientific evidence',
    template: '%s | Bio Nexus',
  },
  description,
  alternates: {
    canonical: '/',
  },
  openGraph: {
    type: 'website',
    url: '/',
    siteName: SITE_NAME,
    title: 'Bio Nexus — Bioinformatics analysis with traceable scientific evidence',
    description,
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Bio Nexus — Bioinformatics analysis with traceable scientific evidence',
    description,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <head>
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
                  'Bio Nexus unifies bioinformatics analysis, scientific provenance, visualization and evidence-backed interpretation in a single research workspace.',
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
