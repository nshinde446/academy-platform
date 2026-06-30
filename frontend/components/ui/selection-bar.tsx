"use client";

import { Button } from "@/components/ui/button";

interface SelectionBarProps {
  count: number;
  /** Singular noun for the selected rows, e.g. "course". */
  noun: string;
  pending?: boolean;
  onDelete: () => void;
  onClear: () => void;
}

/**
 * Compact "N selected · Delete selected · Clear" bar shown above a table when
 * one or more rows are checked. The select-then-delete counterpart used across
 * the academic sections — explicit selection, never a blind "delete all".
 */
export function SelectionBar({
  count,
  noun,
  pending = false,
  onDelete,
  onClear,
}: SelectionBarProps) {
  if (count === 0) return null;
  const label = count === 1 ? noun : `${noun}s`;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2">
      <span className="text-sm font-medium">
        {count} {label} selected
      </span>
      <Button
        variant="destructive"
        size="sm"
        onClick={onDelete}
        disabled={pending}
      >
        Delete selected
      </Button>
      <Button variant="ghost" size="sm" onClick={onClear} disabled={pending}>
        Clear
      </Button>
    </div>
  );
}
