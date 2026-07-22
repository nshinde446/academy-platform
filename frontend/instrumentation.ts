// Server-side instrumentation. `register` runs once per Next.js server
// instance before it handles requests; `onRequestError` receives server-side
// render errors (see
// node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/instrumentation.md).
//
// No-ops without SENTRY_DSN.

import * as Sentry from "@sentry/nextjs";

import { scrubEvent } from "@/lib/sentry-scrub";

export async function register() {
  const dsn = process.env.SENTRY_DSN;
  if (!dsn) return;

  // The Node and Edge runtimes both load this file; only the Node one applies
  // here, since proxy.ts is the only edge surface and it handles no PII.
  if (process.env.NEXT_RUNTIME === "nodejs") {
    Sentry.init({
      dsn,
      environment: process.env.SENTRY_ENVIRONMENT ?? "production",
      release: process.env.SENTRY_RELEASE,
      tracesSampleRate: 0,
      sendDefaultPii: false,
      beforeSend: scrubEvent,
    });
  }
}

// Next calls this for errors thrown during server rendering. The error may be
// a React-processed wrapper rather than the original throw — `digest` is the
// handle that ties it to what the user was shown by the error boundary.
export const onRequestError = Sentry.captureRequestError;
