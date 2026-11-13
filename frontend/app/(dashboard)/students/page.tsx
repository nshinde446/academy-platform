"use client";

import { useEffect, useState } from "react";
import { useUserStore, useRoles } from "@/store/user-store";
import { useDebounce } from "@/hooks/use-debounce";
import apiClient from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PromptDialog } from "@/components/ui/prompt-dialog";
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  useStudentsRoster,
  useCreateStudent,
  useUpdateStudent,
  useCancelAdmission,
  useBulkUpdateStudents,
  useBulkDeleteStudents,
  useAcademicYears,
} from "./_hooks/use-students";
import { CancelledStudents } from "./_components/cancelled-students";
import { useBatches } from "../batches/_hooks/use-batches";
import type {
  StudentCreate,
  StudentResponse,
  StudentUpdate,
  StudentWithStats,
} from "./_schemas/student";
import { exportRosterCsv, downloadRosterRows } from "./_lib/export-roster";
import {
  type RosterFilters,
  EMPTY_FILTERS,
  hasActiveFilters,
} from "./_lib/saved-views";
import { StudentTable } from "./_components/student-table";
import { RosterFiltersBar } from "./_components/roster-filters";
import { BulkActionBar } from "./_components/bulk-action-bar";
import { StudentEmptyState } from "./_components/student-empty-state";
import { CreateStudentDialog } from "./_components/create-student-dialog";
import { EditStudentDialog } from "./_components/edit-student-dialog";
import { ImportStudentsDialog } from "./_components/import-students-dialog";
import { DeleteAllStudentsDialog } from "./_components/delete-all-students-dialog";

const PAGE_SIZE = 50;

export default function StudentsPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;
  // Delete is Manager-only (RBAC). Hide the destructive controls for others so
  // they don't hit dead-end 403s; the server enforces regardless.
  const { isManager } = useRoles();

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);
  const [filters, setFilters] = useState<RosterFilters>(EMPTY_FILTERS);
  const [page, setPage] = useState(0);
  const [sortBy, setSortBy] = useState("name");
  const [order, setOrder] = useState<"asc" | "desc">("asc");

  // Numeric columns are most useful high-to-low; name reads A→Z. Clicking the
  // active column toggles direction; a new column starts at its natural default.
  function handleSort(key: string) {
    if (key === sortBy) {
      setOrder((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(key);
      setOrder(key === "name" ? "asc" : "desc");
    }
    setPage(0);
  }

  const [exporting, setExporting] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<StudentResponse | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  // Active roster vs the Cancelled Students tab (Point 4).
  const [view, setView] = useState<"active" | "cancelled">("active");
  // The student whose admission is being cancelled (opens the reason prompt).
  const [cancelTarget, setCancelTarget] = useState<StudentWithStats | null>(
    null
  );

  // A new search or filter resets to the first page.
  useEffect(() => {
    setPage(0);
  }, [debouncedSearch, filters]);

  const statsQuery = useStudentsRoster(branchId, {
    offset: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    search: debouncedSearch,
    sortBy,
    order,
    standard: filters.standard,
    targetExam: filters.targetExam,
    feesStatus: filters.feesStatus,
    batchId: filters.batchId,
  });
  const academicYearsQuery = useAcademicYears(branchId);
  const batchesQuery = useBatches(branchId);
  const createMutation = useCreateStudent(branchId);
  const updateMutation = useUpdateStudent(branchId);
  const cancelMutation = useCancelAdmission(branchId);
  const bulkUpdateMutation = useBulkUpdateStudents(branchId);
  const bulkDeleteMutation = useBulkDeleteStudents(branchId);

  const rows = statsQuery.data?.items ?? [];
  const total = statsQuery.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const from = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const to = Math.min(total, (page + 1) * PAGE_SIZE);

  async function handleCreate(data: Omit<StudentCreate, "branch_id">) {
    if (!branchId) return;
    await createMutation.mutateAsync({ ...data, branch_id: branchId });
  }

  // The stats row omits some fields the edit form needs, so fetch the full
  // record on demand rather than holding every student in memory.
  async function handleEdit(row: StudentWithStats) {
    if (!branchId) return;
    const res = await apiClient.get<StudentResponse>(
      `/api/v1/students/${row.id}`,
      { params: { branch_id: branchId } }
    );
    setEditTarget(res.data);
    setEditOpen(true);
  }

  async function handleUpdate(data: StudentUpdate) {
    if (!editTarget) return;
    await updateMutation.mutateAsync({ studentId: editTarget.id, data });
  }

  // Generic inline-cell edit (stream / class / fees) — one PATCH per change.
  function handleFieldChange(
    student: StudentWithStats,
    patch: Partial<StudentUpdate>
  ) {
    updateMutation.mutate({ studentId: student.id, data: patch });
  }

  function handleCancelClick(student: StudentWithStats) {
    setCancelTarget(student);
  }

  async function handleCancelConfirm(reason: string) {
    if (!cancelTarget) return;
    await cancelMutation.mutateAsync({
      studentId: cancelTarget.id,
      reason: reason || null,
    });
    setCancelTarget(null);
  }

  async function handleExport() {
    if (!branchId) return;
    setExporting(true);
    try {
      await exportRosterCsv(branchId, {
        search: debouncedSearch,
        sortBy,
        order,
        standard: filters.standard,
        targetExam: filters.targetExam,
        feesStatus: filters.feesStatus,
        batchId: filters.batchId,
      });
    } finally {
      setExporting(false);
    }
  }

  // --- Selection + bulk actions ---
  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    setSelectedIds((prev) => {
      const allOnPage = rows.every((r) => prev.has(r.id));
      const next = new Set(prev);
      if (allOnPage) rows.forEach((r) => next.delete(r.id));
      else rows.forEach((r) => next.add(r.id));
      return next;
    });
  }

  function clearSelection() {
    setSelectedIds(new Set());
  }

  async function handleBulkPatch(patch: Partial<StudentUpdate>) {
    if (selectedIds.size === 0) return;
    await bulkUpdateMutation.mutateAsync({
      student_ids: [...selectedIds],
      ...patch,
    });
  }

  async function handleBulkAssignBatch(batchId: string) {
    if (selectedIds.size === 0) return;
    await bulkUpdateMutation.mutateAsync({
      student_ids: [...selectedIds],
      batch_id: batchId,
    });
  }

  function handleExportSelected() {
    // Export the selected rows we currently have loaded (the visible page).
    downloadRosterRows(rows.filter((r) => selectedIds.has(r.id)));
  }

  async function handleBulkDeleteConfirm() {
    await bulkDeleteMutation.mutateAsync([...selectedIds]);
    clearSelection();
  }


  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Students"
        description="Manage student records for your branch."
        actions={
          <>
            {branchId && isManager && (
              <DeleteAllStudentsDialog branchId={branchId} count={total} />
            )}
            {branchId && (
              <Button
                variant="outline"
                onClick={handleExport}
                disabled={exporting || total === 0}
              >
                {exporting ? "Exporting…" : "Export CSV"}
              </Button>
            )}
            {branchId && <ImportStudentsDialog branchId={branchId} />}
            <CreateStudentDialog
              academicYears={academicYearsQuery.data ?? []}
              onSubmit={handleCreate}
              isPending={createMutation.isPending}
            />
          </>
        }
      />

      {/* Active roster vs Cancelled Students tab (Point 4). */}
      <div className="flex gap-1 rounded-lg border p-1 w-fit">
        <Button
          size="sm"
          variant={view === "active" ? "default" : "ghost"}
          onClick={() => setView("active")}
        >
          Active
        </Button>
        <Button
          size="sm"
          variant={view === "cancelled" ? "default" : "ghost"}
          onClick={() => setView("cancelled")}
        >
          Cancelled
        </Button>
      </div>

      {view === "cancelled" ? (
        <CancelledStudents branchId={branchId} canRestore={isManager} />
      ) : (
      <>
      {/* Search */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="Search by name or enrollment number..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:max-w-sm"
        />
        <span className="text-sm text-muted-foreground">
          {total} student{total !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Filters + Saved Views */}
      {branchId && (
        <RosterFiltersBar
          branchId={branchId}
          filters={filters}
          onChange={setFilters}
          batches={batchesQuery.data ?? []}
        />
      )}

      {/* Content */}
      {statsQuery.isLoading ? (
        <TableSkeleton rows={8} />
      ) : statsQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to load students. Make sure the backend is running.
        </p>
      ) : total === 0 ? (
        <StudentEmptyState
          hasSearch={!!debouncedSearch || hasActiveFilters(filters)}
        />
      ) : (
        <>
          {selectedIds.size > 0 && (
            <BulkActionBar
              count={selectedIds.size}
              batches={batchesQuery.data ?? []}
              pending={
                bulkUpdateMutation.isPending || bulkDeleteMutation.isPending
              }
              onSetFees={(v) => handleBulkPatch({ fees_status: v as StudentUpdate["fees_status"] })}
              onSetClass={(v) => handleBulkPatch({ standard: v as StudentUpdate["standard"] })}
              onSetStream={(v) => handleBulkPatch({ stream: v as StudentUpdate["stream"] })}
              onAssignBatch={handleBulkAssignBatch}
              onExport={handleExportSelected}
              onDelete={isManager ? () => setBulkDeleteOpen(true) : undefined}
              onClear={clearSelection}
            />
          )}
          <StudentTable
            rows={rows}
            onEdit={handleEdit}
            onCancel={isManager ? handleCancelClick : undefined}
            onFieldChange={handleFieldChange}
            sortBy={sortBy}
            order={order}
            onSort={handleSort}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelect}
            onToggleSelectAll={toggleSelectAll}
          />
          {/* Pagination */}
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm text-muted-foreground">
              Showing {from}–{to} of {total}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0 || statsQuery.isFetching}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                Previous
              </Button>
              <span className="text-sm text-muted-foreground tabular-nums">
                Page {page + 1} of {pageCount}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page + 1 >= pageCount || statsQuery.isFetching}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
      </>
      )}

      <EditStudentDialog
        student={editTarget}
        open={editOpen}
        onOpenChange={setEditOpen}
        onSubmit={handleUpdate}
        isPending={updateMutation.isPending}
      />

      {/* Cancel Admission (Point 4): keeps the record, captures an optional
          reason. Today's date is recorded server-side. */}
      <PromptDialog
        open={!!cancelTarget}
        onOpenChange={(o) => !o && setCancelTarget(null)}
        title="Cancel admission?"
        description={
          cancelTarget
            ? `"${cancelTarget.first_name} ${cancelTarget.last_name}" will be removed from active lists but kept under Cancelled Students, with all past results and fees intact. You can restore them later.`
            : ""
        }
        label="Reason (optional)"
        placeholder="e.g. Shifted city, admission withdrawn"
        confirmLabel="Cancel admission"
        onConfirm={handleCancelConfirm}
      />

      <ConfirmDialog
        open={bulkDeleteOpen}
        onOpenChange={setBulkDeleteOpen}
        title={`Delete ${selectedIds.size} student(s)?`}
        description={`This soft-deletes the ${selectedIds.size} selected student(s). They can be restored by re-importing.`}
        confirmLabel="Delete selected"
        destructive
        onConfirm={handleBulkDeleteConfirm}
      />
    </div>
  );
}
