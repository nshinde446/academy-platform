// Client-side instrumentation. Next 16 runs this file before the app becomes
// interactive; no specific export is required (see
// node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/instrumentation-client.md).
//
// No-ops without NEXT_PUBLIC_SENTRY_DSN, so local dev and any deploy without
// the secret configured send nothing.

import * as Sentry from "@sentry/nextjs";

import { scrubEvent } from "@/lib/sentry-scrub";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? "production",
    release: process.env.NEXT_PUBLIC_SENTRY_RELEASE,

    // Errors are the point. Tracing and session replay are the expensive part
    // of the quota, and replay in particular would record student data on
    // screen — exactly what the scrubbing exists to prevent.
    tracesSampleRate: 0,

    // Never let the SDK attach IPs, cookies or headers on its own.
    sendDefaultPii: false,

    beforeSend: scrubEvent,
  });
}

// Ties client-side navigations to the correct transaction. Exported
// unconditionally: Next expects a stable module shape, and the call is inert
// when Sentry was never initialised.
export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
