"use client";

import { useMemo, useState } from "react";
import { useUserStore } from "@/store/user-store";
import { useDebounce } from "@/hooks/use-debounce";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/layout/page-header";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { SelectionBar } from "@/components/ui/selection-bar";
import { useToast } from "@/components/ui/toast";
import { useRowSelection } from "@/hooks/use-row-selection";
import { runBulkDelete, summarizeBulkDelete } from "@/lib/bulk-delete";
import {
  useAcademicYears,
  useBatches,
  useCourses,
  useCreateAcademicYear,
  useCreateBatch,
  useDeleteBatch,
  useUpdateBatch,
} from "./_hooks/use-batches";
import type {
  BatchCreate,
  BatchResponse,
  BatchUpdate,
} from "./_schemas/batch";
import { BatchTable } from "./_components/batch-table";
import { BatchEmptyState } from "./_components/batch-empty-state";
import { CreateBatchDialog } from "./_components/create-batch-dialog";
import { EditBatchDialog } from "./_components/edit-batch-dialog";

function filterBatches(
  batches: BatchResponse[],
  query: string,
  yearStartYearLookup: Record<string, number>,
  filterYearStart: number | null
): BatchResponse[] {
  let list = batches;
  if (filterYearStart !== null) {
    list = list.filter((b) => {
      const start = yearStartYearLookup[b.start_academic_year_id];
      const end = yearStartYearLookup[b.end_academic_year_id];
      if (start === undefined || end === undefined) return false;
      return start <= filterYearStart && filterYearStart <= end;
    });
  }
  if (!query) return list;
  const q = query.toLowerCase();
  return list.filter(
    (b) =>
      b.name.toLowerCase().includes(q) || b.code.toLowerCase().includes(q)
  );
}

export default function BatchesPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);
  const [selectedYearId, setSelectedYearId] = useState<string>("");
  const [editTarget, setEditTarget] = useState<BatchResponse | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<BatchResponse | null>(null);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);

  const toast = useToast();
  const selection = useRowSelection();

  const batchesQuery = useBatches(branchId);
  const academicYearsQuery = useAcademicYears(branchId);
  const coursesQuery = useCourses(branchId);
  const createMutation = useCreateBatch(branchId);
  const updateMutation = useUpdateBatch(branchId);
  const deleteMutation = useDeleteBatch(branchId);
  const createYearMutation = useCreateAcademicYear(branchId);

  const academicYears = academicYearsQuery.data ?? [];
  const courses = coursesQuery.data ?? [];

  const sortedYears = useMemo(
    () => [...academicYears].sort((a, b) => a.start_year - b.start_year),
    [academicYears]
  );

  const yearStartYearLookup = useMemo(() => {
    const map: Record<string, number> = {};
    for (const y of academicYears) map[y.id] = y.start_year;
    return map;
  }, [academicYears]);

  const filterYearStart =
    selectedYearId && yearStartYearLookup[selectedYearId] !== undefined
      ? yearStartYearLookup[selectedYearId]
      : null;

  const filtered = useMemo(
    () =>
      filterBatches(
        batchesQuery.data ?? [],
        debouncedSearch,
        yearStartYearLookup,
        filterYearStart
      ),
    [batchesQuery.data, debouncedSearch, yearStartYearLookup, filterYearStart]
  );

  async function handleCreate(data: Omit<BatchCreate, "branch_id">) {
    if (!branchId) return;
    await createMutation.mutateAsync({ ...data, branch_id: branchId });
  }

  async function handleCreateAcademicYear(startYear: number) {
    return createYearMutation.mutateAsync(startYear);
  }

  function handleEdit(batch: BatchResponse) {
    setEditTarget(batch);
    setEditOpen(true);
  }

  async function handleUpdate(data: BatchUpdate) {
    if (!editTarget) return;
    await updateMutation.mutateAsync({ batchId: editTarget.id, data });
  }

  function handleDeleteClick(batch: BatchResponse) {
    setDeleteTarget(batch);
  }

  async function handleDeleteConfirm() {
    if (!deleteTarget) return;
    await deleteMutation.mutateAsync(deleteTarget.id);
  }

  async function handleBulkDeleteConfirm() {
    const result = await runBulkDelete(selection.selected, (id) =>
      deleteMutation.mutateAsync(id)
    );
    selection.clear();
    const summary = summarizeBulkDelete(result, "batch");
    if (result.failed.length > 0) toast.info("Bulk delete", summary);
    else toast.success("Bulk delete", summary);
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Batches"
        description="Manage batch groups. Multi-year courses span academic years automatically."
        actions={
          <CreateBatchDialog
            academicYears={sortedYears}
            courses={courses}
            onSubmit={handleCreate}
            onCreateAcademicYear={handleCreateAcademicYear}
            isPending={createMutation.isPending}
          />
        }
      />

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="Search by name or code..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:max-w-sm"
        />
        {sortedYears.length > 0 && (
          <select
            value={selectedYearId}
            onChange={(e) => setSelectedYearId(e.target.value)}
            className="h-9 rounded-lg border border-input bg-background px-3 text-sm"
            aria-label="Filter by academic year"
          >
            <option value="">All academic years</option>
            {sortedYears.map((y) => (
              <option key={y.id} value={y.id}>
                {y.name}
              </option>
            ))}
          </select>
        )}
        <span className="text-sm text-muted-foreground">
          {filtered.length} batch{filtered.length !== 1 ? "es" : ""}
        </span>
      </div>

      <SelectionBar
        count={selection.count}
        noun="batch"
        pending={deleteMutation.isPending}
        onDelete={() => setBulkDeleteOpen(true)}
        onClear={selection.clear}
      />

      {/* Content */}
      {batchesQuery.isLoading ? (
        <p className="text-muted-foreground text-sm">Loading batches...</p>
      ) : batchesQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to load batches. Make sure the backend is running.
        </p>
      ) : filtered.length === 0 ? (
        <BatchEmptyState hasSearch={!!debouncedSearch || !!selectedYearId} />
      ) : (
        <BatchTable
          batches={filtered}
          courses={courses}
          academicYears={academicYears}
          onEdit={handleEdit}
          onDelete={handleDeleteClick}
          selectedIds={selection.selectedIds}
          onToggleSelect={selection.toggle}
          onToggleSelectAll={() => selection.toggleAll(filtered.map((b) => b.id))}
        />
      )}

      <EditBatchDialog
        batch={editTarget}
        open={editOpen}
        onOpenChange={setEditOpen}
        onSubmit={handleUpdate}
        isPending={updateMutation.isPending}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title="Delete batch?"
        description={
          deleteTarget
            ? `Are you sure you want to delete "${deleteTarget.name}"? This cannot be undone.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteConfirm}
      />

      <ConfirmDialog
        open={bulkDeleteOpen}
        onOpenChange={setBulkDeleteOpen}
        title={`Delete ${selection.count} batch${selection.count !== 1 ? "es" : ""}?`}
        description="This cannot be undone. Batches that still have enrolled students or dependent records are skipped and reported."
        confirmLabel={`Delete ${selection.count}`}
        destructive
        onConfirm={handleBulkDeleteConfirm}
      />
    </div>
  );
}
