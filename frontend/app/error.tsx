"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/ui/error-state";

/**
 * Boundary for everything under the root layout that is *not* the dashboard —
 * i.e. `/login` — plus any crash in `app/(dashboard)/layout.tsx` itself, which
 * the dashboard's own error.tsx sits below and therefore cannot catch.
 */
export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Client-side crashes never reach the server logs on their own. Until a
    // real reporter (Sentry/OTel) is wired up, at least land it in the browser
    // console with a stable prefix so it is greppable in a screen-share.
    console.error("[boundary:root]", error);
  }, [error]);

  return <ErrorState digest={error.digest} onRetry={() => reset()} />;
}
