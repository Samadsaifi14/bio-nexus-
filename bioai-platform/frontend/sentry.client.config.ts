import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || '',
  environment: process.env.NEXT_PUBLIC_VERCEL_ENV || 'development',
  tracesSampleRate: 0.1,
  integrations: [Sentry.browserTracingIntegration()],
  beforeSend(event) {
    if (event.exception) {
      console.error('[Sentry] Captured exception:', event.exception.values?.[0]?.value);
    }
    return event;
  },
});
