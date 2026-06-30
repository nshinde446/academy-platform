"use client";

import { useCallback, useMemo, useState } from "react";

/**
 * Generic row-selection model for "select-then-act" bulk operations.
 *
 * Tracks a Set of selected ids and exposes the toggles a table needs:
 * per-row toggle, header "select all on this page" toggle, and clear.
 * Kept deliberately dumb (just ids) so every section — courses, batches,
 * lectures, … — can share one selection contract instead of re-deriving it.
 */
export function useRowSelection() {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const toggle = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // Toggle every id on the current page: if all are already selected, clear
  // them; otherwise add them. Operates on whatever ids the caller passes, so
  // it respects the current filter/page rather than the whole dataset.
  const toggleAll = useCallback((pageIds: string[]) => {
    setSelectedIds((prev) => {
      const allOn = pageIds.length > 0 && pageIds.every((id) => prev.has(id));
      const next = new Set(prev);
      if (allOn) pageIds.forEach((id) => next.delete(id));
      else pageIds.forEach((id) => next.add(id));
      return next;
    });
  }, []);

  const clear = useCallback(() => setSelectedIds(new Set()), []);

  const isSelected = useCallback(
    (id: string) => selectedIds.has(id),
    [selectedIds],
  );

  const selected = useMemo(() => [...selectedIds], [selectedIds]);

  return {
    selectedIds,
    selected,
    count: selectedIds.size,
    isSelected,
    toggle,
    toggleAll,
    clear,
  };
}

export type RowSelection = ReturnType<typeof useRowSelection>;
