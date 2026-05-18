interface BatchEmptyStateProps {
  hasSearch: boolean;
}

export function BatchEmptyState({ hasSearch }: BatchEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-16">
      <p className="text-muted-foreground">
        {hasSearch ? "No batches match your search." : "No batches yet."}
      </p>
      {!hasSearch && (
        <p className="text-sm text-muted-foreground mt-1">
          Click &quot;Create Batch&quot; to add one.
        </p>
      )}
    </div>
  );
}
