import { Skeleton, TableSkeleton } from "@/components/ui/skeleton";

/**
 * Shown while a dashboard route segment streams in — chiefly the first
 * navigation to a section, when its JS chunk is still downloading.
 *
 * Mirrors the shape every list page settles into (compact PageHeader + a
 * bordered table) so the swap to real content doesn't shift layout. Pages that
 * aren't list-shaped can drop their own `loading.tsx` alongside `page.tsx` to
 * override this.
 */
export default function DashboardLoading() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading…</span>
      <div className="flex items-center justify-between gap-3">
        <Skeleton className="h-6 w-44" />
        <Skeleton className="h-8 w-28" />
      </div>
      <TableSkeleton rows={8} />
    </div>
  );
}
