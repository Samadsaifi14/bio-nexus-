import { withSentryConfig } from '@sentry/nextjs';

/** @type {import('next').NextConfig} */
const nextConfig = {
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
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/backend/:path*',
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

// Force clean Vercel rebuild — reads NEXT_PUBLIC_API_URL at build time
export default withSentryConfig(nextConfig, {
  silent: true,
  hideSourceMaps: true,
});
