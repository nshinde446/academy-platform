interface AcademicYearEmptyStateProps {
  hasSearch: boolean;
}

export function AcademicYearEmptyState({
  hasSearch,
}: AcademicYearEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-16">
      <p className="text-muted-foreground">
        {hasSearch
          ? "No academic years match your search."
          : "No academic years yet."}
      </p>
      {!hasSearch && (
        <p className="text-sm text-muted-foreground mt-1">
          Click &quot;Create Academic Year&quot; to add one.
        </p>
      )}
    </div>
  );
}
