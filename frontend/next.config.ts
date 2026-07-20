import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

// In dev:  unset → proxies /api/* to http://localhost:8000
// On Vercel: set API_BASE_URL=https://api.<yourdomain> in project env vars
const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_BASE_URL}/api/:path*`,
      },
      // BioMax/ZKTeco devices push to a fixed /iclock/* path. Proxy it to the
      // backend so devices can use the public app host as their server URL.
      {
        source: "/iclock/:path*",
        destination: `${API_BASE_URL}/iclock/:path*`,
      },
    ];
  },
};

// Wrap for Sentry: uploads source maps at build time so production stacks are
// readable frames instead of minified soup, then deletes them from the bundle
// so they are not publicly served.
//
// Upload only happens when SENTRY_AUTH_TOKEN and the org/project are present.
// Without them the wrapper is a no-op passthrough, so local builds, CI, and
// any deploy without the secrets behave exactly as before.
export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,

  // Keep build logs quiet unless something actually fails.
  silent: !process.env.CI,

  // Source maps are uploaded, then removed from the client bundle — otherwise
  // anyone could fetch them and read the app source.
  sourcemaps: { deleteSourcemapsAfterUpload: true },

  // Route the browser SDK's requests through the app's own origin, so
  // ad-blockers don't silently swallow error reports.
  tunnelRoute: "/monitoring",

  // A missing/expired auth token must not fail a production deploy — losing
  // source maps is worse than nothing, but losing the release is worse still.
  errorHandler: (err) => {
    console.warn("[sentry] source map upload skipped:", err.message);
  },
});
