const { withSentryConfig } = require('@sentry/nextjs');

/** @type {import('next').NextConfig} */
const nextConfig = {
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
module.exports = withSentryConfig(nextConfig, {
  silent: true,
  hideSourceMaps: true,
});
