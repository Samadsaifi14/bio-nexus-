import type { MetadataRoute } from 'next';
import { SITE_URL } from '@/lib/seo';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: ['/', '/analyze/', '/learn/', '/wizard/'],
        disallow: [
          '/api/',
          '/auth/',
          '/dashboard/',
          '/jobs/',
          '/results/',
          '/report/',
          '/settings/',
          '/share/',
        ],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
