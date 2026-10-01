import { withSentryConfig } from '@sentry/nextjs';

/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=(), payment=()',
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
        ],
      },
    ];
  },
  // Next.js 16.3 + Vercel's build adapter currently fails after a successful
  // Turbopack build when standalone output is enabled because the adapter no
  // longer emits .next/next-server.js.nft.json while the standalone finalize
  // step still expects it. Vercel does not consume the standalone directory,
  // so disable it only there and keep standalone output for local/container use.
  output: process.env.VERCEL ? undefined : 'standalone',
  turbopack: {
    root: import.meta.dirname,
  },
  async rewrites() {
    // Production must never proxy API calls to localhost. A newly-created
    // Vercel project may not yet have NEXT_PUBLIC_API_URL configured, so use
    // the canonical Bio Nexus API endpoint as the Vercel-safe fallback.
    const backendUrl =
      process.env.NEXT_PUBLIC_API_URL ||
      (process.env.VERCEL
        ? 'https://samad14-bio-nexus-api.hf.space'
        : 'http://localhost:8000');

    return [
      {
        source: '/api/backend/:path*',
        destination: `${backendUrl.replace(/\/$/, '')}/:path*`,
      },
    ];
  },
};

export default withSentryConfig(nextConfig, {
  silent: true,
  hideSourceMaps: true,
});
