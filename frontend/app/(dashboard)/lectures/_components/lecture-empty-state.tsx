"use client";

interface LectureEmptyStateProps {
  hasFilter: boolean;
}

export function LectureEmptyState({ hasFilter }: LectureEmptyStateProps) {
  return (
    <div className="rounded-xl border border-dashed p-10 text-center">
      <p className="text-sm font-medium">
        {hasFilter ? "No lectures match your filters." : "No lectures yet."}
      </p>
      <p className="text-sm text-muted-foreground mt-1">
        {hasFilter
          ? "Try clearing or widening the filters."
          : "Click “Schedule Lecture” to create one."}
      </p>
    </div>
  );
}
