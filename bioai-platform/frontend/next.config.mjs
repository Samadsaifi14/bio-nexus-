import { withSentryConfig } from '@sentry/nextjs';

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
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
