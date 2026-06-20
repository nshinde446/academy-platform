"use client";

import { useEffect, useState } from "react";
import { useUserStore } from "@/store/user-store";
import { useDebounce } from "@/hooks/use-debounce";
import apiClient from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  useStudentsRoster,
  useCreateStudent,
  useUpdateStudent,
  useDeleteStudent,
  useAcademicYears,
} from "./_hooks/use-students";
import type {
  Stream,
  StudentCreate,
  StudentResponse,
  StudentUpdate,
  StudentWithStats,
} from "./_schemas/student";
import { StudentTable } from "./_components/student-table";
import { StudentEmptyState } from "./_components/student-empty-state";
import { CreateStudentDialog } from "./_components/create-student-dialog";
import { EditStudentDialog } from "./_components/edit-student-dialog";
import { ImportStudentsDialog } from "./_components/import-students-dialog";
import { DeleteAllStudentsDialog } from "./_components/delete-all-students-dialog";

const PAGE_SIZE = 50;

export default function StudentsPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);
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

  const [editTarget, setEditTarget] = useState<StudentResponse | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<StudentWithStats | null>(
    null
  );

  // A new search resets to the first page.
  useEffect(() => {
    setPage(0);
  }, [debouncedSearch]);

  const statsQuery = useStudentsRoster(branchId, {
    offset: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    search: debouncedSearch,
    sortBy,
    order,
  });
  const academicYearsQuery = useAcademicYears(branchId);
  const createMutation = useCreateStudent(branchId);
  const updateMutation = useUpdateStudent(branchId);
  const deleteMutation = useDeleteStudent(branchId);

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

  function handleStreamChange(student: StudentWithStats, stream: Stream) {
    updateMutation.mutate({ studentId: student.id, data: { stream } });
  }

  function handleDeleteClick(student: StudentWithStats) {
    setDeleteTarget(student);
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
          <h2 className="text-2xl font-semibold">Students</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage student records for your branch
          </p>
        </div>
        <div className="flex gap-2">
          {branchId && (
            <DeleteAllStudentsDialog branchId={branchId} count={total} />
          )}
          {branchId && <ImportStudentsDialog branchId={branchId} />}
          <CreateStudentDialog
            academicYears={academicYearsQuery.data ?? []}
            onSubmit={handleCreate}
            isPending={createMutation.isPending}
          />
        </div>
      </div>

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

      {/* Content */}
      {statsQuery.isLoading ? (
        <p className="text-muted-foreground text-sm">Loading students...</p>
      ) : statsQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to load students. Make sure the backend is running.
        </p>
      ) : total === 0 ? (
        <StudentEmptyState hasSearch={!!debouncedSearch} />
      ) : (
        <>
          <StudentTable
            rows={rows}
            onEdit={handleEdit}
            onDelete={handleDeleteClick}
            onStreamChange={handleStreamChange}
            sortBy={sortBy}
            order={order}
            onSort={handleSort}
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

      <EditStudentDialog
        student={editTarget}
        open={editOpen}
        onOpenChange={setEditOpen}
        onSubmit={handleUpdate}
        isPending={updateMutation.isPending}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title="Delete student?"
        description={
          deleteTarget
            ? `Are you sure you want to delete "${deleteTarget.first_name} ${deleteTarget.last_name}"? This cannot be undone.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
