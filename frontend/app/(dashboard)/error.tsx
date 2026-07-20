"use client";

import { useEffect } from "react";
import * as Sentry from "@sentry/nextjs";

import { ErrorState } from "@/components/ui/error-state";
import { Button } from "@/components/ui/button";

/**
 * Boundary for every dashboard route. Because it lives *inside* the
 * `(dashboard)` group it renders in place of the page content while the
 * layout — sidebar, toasts — stays mounted, so a crash in one section leaves
 * the rest of the app navigable instead of blanking the window.
 */
export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Report before logging: the console line is only visible to whoever has
    // devtools open, which in production is nobody. `digest` is attached as a
    // tag so the reference shown to the user resolves to this event.
    Sentry.captureException(error, {
      tags: { boundary: "dashboard", digest: error.digest ?? "none" },
    });
    console.error("[boundary:dashboard]", error);
  }, [error]);

  return (
    <ErrorState
      title="This page failed to load"
      description="The rest of the app is still working — you can retry, or pick another section from the sidebar."
      digest={error.digest}
      onRetry={() => reset()}
      action={
        <Button variant="outline" onClick={() => window.location.reload()}>
          Reload page
        </Button>
      }
    />
  );
}
