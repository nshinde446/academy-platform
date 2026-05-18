"use client";

import { useMemo, useState } from "react";
import { useUserStore } from "@/store/user-store";
import { useDebounce } from "@/hooks/use-debounce";
import { Input } from "@/components/ui/input";
import {
  useBatches,
  useCreateBatch,
  useAcademicYears,
  useCourses,
} from "./_hooks/use-batches";
import type { BatchCreate, BatchResponse } from "./_schemas/batch";
import { BatchTable } from "./_components/batch-table";
import { BatchEmptyState } from "./_components/batch-empty-state";
import { CreateBatchDialog } from "./_components/create-batch-dialog";

function filterBatches(
  batches: BatchResponse[],
  query: string
): BatchResponse[] {
  if (!query) return batches;
  const q = query.toLowerCase();
  return batches.filter(
    (b) =>
      b.name.toLowerCase().includes(q) || b.code.toLowerCase().includes(q)
  );
}

export default function BatchesPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);

  const batchesQuery = useBatches(branchId);
  const academicYearsQuery = useAcademicYears(branchId);
  const activeYearId = academicYearsQuery.data?.[0]?.id;
  const coursesQuery = useCourses(branchId, activeYearId);
  const createMutation = useCreateBatch(branchId);

  const filtered = useMemo(
    () => filterBatches(batchesQuery.data ?? [], debouncedSearch),
    [batchesQuery.data, debouncedSearch]
  );

  async function handleCreate(data: Omit<BatchCreate, "branch_id">) {
    if (!branchId) return;
    await createMutation.mutateAsync({ ...data, branch_id: branchId });
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Batches</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage batch groups for courses and schedules
          </p>
        </div>
        <CreateBatchDialog
          academicYears={academicYearsQuery.data ?? []}
          courses={coursesQuery.data ?? []}
          onSubmit={handleCreate}
          isPending={createMutation.isPending}
        />
      </div>

      {/* Search */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="Search by name or code..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:max-w-sm"
        />
        <span className="text-sm text-muted-foreground">
          {filtered.length} batch{filtered.length !== 1 ? "es" : ""}
        </span>
      </div>

      {/* Content */}
      {batchesQuery.isLoading ? (
        <p className="text-muted-foreground text-sm">Loading batches...</p>
      ) : batchesQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to load batches. Make sure the backend is running.
        </p>
      ) : filtered.length === 0 ? (
        <BatchEmptyState hasSearch={!!debouncedSearch} />
      ) : (
        <BatchTable batches={filtered} />
      )}
    </div>
  );
}
