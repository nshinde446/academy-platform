interface TeacherEmptyStateProps {
  hasSearch: boolean;
}

export function TeacherEmptyState({ hasSearch }: TeacherEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-16">
      <p className="text-muted-foreground">
        {hasSearch ? "No teachers match your search." : "No teachers yet."}
      </p>
      {!hasSearch && (
        <p className="text-sm text-muted-foreground mt-1">
          Click &quot;Create Teacher&quot; to add one, or import from a file.
        </p>
      )}
    </div>
  );
}
