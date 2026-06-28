import { cn } from "@/lib/utils"

/** A single shimmering placeholder block. Compose these to mirror the
 * shape of the content that's loading, so the page doesn't flash from
 * blank → text → real data. */
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  )
}

/**
 * Placeholder for a loading table — a header strip plus `rows` greyed-out
 * lines, wrapped in the same bordered card the real tables use so the
 * swap to live data doesn't shift layout.
 */
function TableSkeleton({
  rows = 8,
  className,
}: {
  rows?: number
  className?: string
}) {
  return (
    <div
      className={cn(
        "rounded-xl border ring-1 ring-foreground/10 overflow-hidden",
        className,
      )}
      aria-busy="true"
      aria-live="polite"
    >
      <div className="flex items-center gap-4 border-b bg-muted/40 px-3 py-2.5">
        <Skeleton className="h-3.5 w-24" />
        <Skeleton className="h-3.5 w-16" />
        <Skeleton className="ml-auto h-3.5 w-20" />
      </div>
      <div className="divide-y">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 px-3 py-3">
            <Skeleton className="h-7 w-7 shrink-0 rounded-full" />
            <Skeleton className="h-3.5 w-40" />
            <Skeleton className="hidden h-3.5 w-16 sm:block" />
            <Skeleton className="ml-auto h-7 w-24" />
          </div>
        ))}
      </div>
    </div>
  )
}

export { Skeleton, TableSkeleton }
