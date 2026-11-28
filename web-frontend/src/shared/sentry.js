import * as Sentry from '@sentry/react'

// Imported first by every page entry. Catches uncaught errors and unhandled promise rejections by default.
// MODE is "development" under `vite`, "production" in `vite build`; VITE_SENTRY_ENVIRONMENT overrides it (e.g. staging).
const dsn = import.meta.env.VITE_SENTRY_DSN
if (dsn) {
  Sentry.init({
    dsn,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || import.meta.env.MODE,
    sendDefaultPii: false,
    initialScope: { tags: { app: 'web' } },
  })
}

// React 19 root error hooks: render errors that error boundaries catch, or that nothing catches, reach Sentry too.
export const rootOptions = {
  onUncaughtError: Sentry.reactErrorHandler(),
  onCaughtError: Sentry.reactErrorHandler(),
  onRecoverableError: Sentry.reactErrorHandler(),
}
