interface ClassroomEmptyStateProps {
  hasSearch: boolean;
}

export function ClassroomEmptyState({ hasSearch }: ClassroomEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-16">
      <p className="text-muted-foreground">
        {hasSearch
          ? "No classrooms match your search."
          : "No classrooms yet."}
      </p>
      {!hasSearch && (
        <p className="text-sm text-muted-foreground mt-1">
          Click &quot;Create Classroom&quot; to add one. Offline lectures need
          at least one.
        </p>
      )}
    </div>
  );
}
