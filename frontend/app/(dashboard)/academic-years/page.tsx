"use client";

import { useMemo, useState } from "react";
import { useUserStore } from "@/store/user-store";
import { useDebounce } from "@/hooks/use-debounce";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  useAcademicYears,
  useCreateAcademicYear,
  useDeleteAcademicYear,
} from "./_hooks/use-academic-years";
import type {
  AcademicYearCreate,
  AcademicYearResponse,
} from "./_schemas/academic-year";
import { AcademicYearTable } from "./_components/academic-year-table";
import { AcademicYearEmptyState } from "./_components/academic-year-empty-state";
import { CreateAcademicYearDialog } from "./_components/create-academic-year-dialog";

function filterYears(
  years: AcademicYearResponse[],
  query: string
): AcademicYearResponse[] {
  if (!query) return years;
  const q = query.toLowerCase();
  return years.filter(
    (y) =>
      y.name.toLowerCase().includes(q) ||
      String(y.start_year).includes(q) ||
      String(y.end_year).includes(q)
  );
}

export default function AcademicYearsPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);
  const [deleteTarget, setDeleteTarget] = useState<AcademicYearResponse | null>(
    null
  );

  const yearsQuery = useAcademicYears(branchId);
  const createMutation = useCreateAcademicYear(branchId);
  const deleteMutation = useDeleteAcademicYear(branchId);

  const sorted = useMemo(
    () =>
      [...(yearsQuery.data ?? [])].sort((a, b) => a.start_year - b.start_year),
    [yearsQuery.data]
  );

  const filtered = useMemo(
    () => filterYears(sorted, debouncedSearch),
    [sorted, debouncedSearch]
  );

  async function handleCreate(data: Omit<AcademicYearCreate, "branch_id">) {
    if (!branchId) return;
    await createMutation.mutateAsync({ ...data, branch_id: branchId });
  }

  function handleDeleteClick(year: AcademicYearResponse) {
    setDeleteTarget(year);
  }

  async function handleDeleteConfirm() {
    if (!deleteTarget) return;
    await deleteMutation.mutateAsync(deleteTarget.id);
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Academic Years</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage academic year ranges used by courses and batches. Years are
            immutable once created — delete and recreate if a boundary needs to
            change.
          </p>
        </div>
        <CreateAcademicYearDialog
          onSubmit={handleCreate}
          isPending={createMutation.isPending}
        />
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="Search by name or year..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:max-w-sm"
        />
        <span className="text-sm text-muted-foreground">
          {filtered.length} year{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Content */}
      {yearsQuery.isLoading ? (
        <p className="text-muted-foreground text-sm">
          Loading academic years...
        </p>
      ) : yearsQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to load academic years. Make sure the backend is running.
        </p>
      ) : filtered.length === 0 ? (
        <AcademicYearEmptyState hasSearch={!!debouncedSearch} />
      ) : (
        <AcademicYearTable
          academicYears={filtered}
          onDelete={handleDeleteClick}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title="Delete academic year?"
        description={
          deleteTarget
            ? `Are you sure you want to delete "${deleteTarget.name}"? This cannot be undone. Years referenced by existing batches cannot be deleted.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
