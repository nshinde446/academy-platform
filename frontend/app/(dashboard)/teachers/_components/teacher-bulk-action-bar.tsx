"use client";

import { Button } from "@/components/ui/button";

interface TeacherBulkActionBarProps {
  count: number;
  pending: boolean;
  onDelete: () => void;
  onClear: () => void;
}

// Teachers have no inline bulk-settable fields, so this bar is intentionally
// minimal — selection count + Delete + Clear. Mirrors the Students bulk bar's
// shell so the two roster pages feel the same.
export function TeacherBulkActionBar({
  count,
  pending,
  onDelete,
  onClear,
}: TeacherBulkActionBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2">
      <span className="text-sm font-medium">{count} selected</span>
      <div className="ml-auto flex gap-2">
        <Button
          variant="destructive"
          size="sm"
          onClick={onDelete}
          disabled={pending}
        >
          Delete
        </Button>
        <Button variant="ghost" size="sm" onClick={onClear} disabled={pending}>
          Clear
        </Button>
      </div>
    </div>
  );
}
