interface CourseEmptyStateProps {
  hasSearch: boolean;
}

export function CourseEmptyState({ hasSearch }: CourseEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-16">
      <p className="text-muted-foreground">
        {hasSearch ? "No courses match your search." : "No courses yet."}
      </p>
      {!hasSearch && (
        <p className="text-sm text-muted-foreground mt-1">
          Click &quot;Create Course&quot; to add one.
        </p>
      )}
    </div>
  );
}
