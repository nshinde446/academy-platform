interface StudentEmptyStateProps {
  hasSearch: boolean;
}

export function StudentEmptyState({ hasSearch }: StudentEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-16">
      <p className="text-muted-foreground">
        {hasSearch ? "No students match your search." : "No students yet."}
      </p>
      {!hasSearch && (
        <p className="text-sm text-muted-foreground mt-1">
          Click &quot;Create Student&quot; to add one, or import from a file.
        </p>
      )}
    </div>
  );
}
