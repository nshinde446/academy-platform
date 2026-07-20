import { TriangleAlert, RotateCw } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * The shared "something broke" panel rendered by every `error.tsx` boundary.
 *
 * Deliberately dumb and dependency-free: an error boundary can be triggered by
 * a crash in almost any part of the tree, so this must not itself depend on
 * react-query, the user store, or anything else that might be the thing that
 * failed.
 *
 * `digest` is the hash Next.js attaches to errors thrown on the server. It is
 * the only handle on a production stack trace (the real message is stripped
 * from the client bundle), so it is surfaced for the user to quote in a bug
 * report rather than hidden.
 */
export function ErrorState({
  title = "Something went wrong",
  description = "This section failed to load. It is usually temporary — try again, and if it keeps happening quote the reference below.",
  digest,
  onRetry,
  retryLabel = "Try again",
  action,
  className,
}: {
  title?: string;
  description?: ReactNode;
  digest?: string;
  onRetry?: () => void;
  retryLabel?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex min-h-[60vh] flex-col items-center justify-center gap-4 px-6 py-12 text-center",
        className,
      )}
    >
      <div className="flex size-11 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <TriangleAlert className="size-5" aria-hidden="true" />
      </div>

      <div className="flex max-w-md flex-col gap-1.5">
        <h2 className="text-base font-semibold tracking-tight">{title}</h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>

      {(onRetry || action) && (
        <div className="flex flex-wrap items-center justify-center gap-2">
          {onRetry && (
            <Button onClick={onRetry}>
              <RotateCw data-icon="inline-start" aria-hidden="true" />
              {retryLabel}
            </Button>
          )}
          {action}
        </div>
      )}

      {digest && (
        <p className="font-mono text-xs text-muted-foreground">
          Reference: {digest}
        </p>
      )}
    </div>
  );
}
