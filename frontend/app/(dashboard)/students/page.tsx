"use client";

import { useMemo, useState } from "react";
import { useUserStore } from "@/store/user-store";
import { useDebounce } from "@/hooks/use-debounce";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  useStudents,
  useStudentsWithStats,
  useCreateStudent,
  useUpdateStudent,
  useDeleteStudent,
  useAcademicYears,
} from "./_hooks/use-students";
import type {
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

function filterStudents(
  rows: StudentWithStats[],
  query: string
): StudentWithStats[] {
  if (!query) return rows;
  const q = query.toLowerCase();
  return rows.filter(
    (s) =>
      `${s.first_name} ${s.last_name}`.toLowerCase().includes(q) ||
      s.enrollment_number?.toLowerCase().includes(q),
  );
}

export default function StudentsPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);

  const [editTarget, setEditTarget] = useState<StudentResponse | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<StudentResponse | null>(
    null
  );

  const studentsQuery = useStudents(branchId);
  const statsQuery = useStudentsWithStats(branchId);
  const academicYearsQuery = useAcademicYears(branchId);
  const createMutation = useCreateStudent(branchId);
  const updateMutation = useUpdateStudent(branchId);
  const deleteMutation = useDeleteStudent(branchId);

  const studentsById = useMemo(() => {
    const map: Record<string, StudentResponse> = {};
    for (const s of studentsQuery.data ?? []) map[s.id] = s;
    return map;
  }, [studentsQuery.data]);

  const filtered = useMemo(
    () => filterStudents(statsQuery.data ?? [], debouncedSearch),
    [statsQuery.data, debouncedSearch]
  );

  async function handleCreate(data: Omit<StudentCreate, "branch_id">) {
    if (!branchId) return;
    await createMutation.mutateAsync({ ...data, branch_id: branchId });
  }

  function handleEdit(student: StudentResponse) {
    setEditTarget(student);
    setEditOpen(true);
  }

  async function handleUpdate(data: StudentUpdate) {
    if (!editTarget) return;
    await updateMutation.mutateAsync({ studentId: editTarget.id, data });
  }

  function handleDeleteClick(student: StudentResponse) {
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
          placeholder="Search by name, email, or enrollment number..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:max-w-sm"
        />
        <span className="text-sm text-muted-foreground">
          {filtered.length} student{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Content */}
      {statsQuery.isLoading || studentsQuery.isLoading ? (
        <p className="text-muted-foreground text-sm">Loading students...</p>
      ) : statsQuery.isError || studentsQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to load students. Make sure the backend is running.
        </p>
      ) : filtered.length === 0 ? (
        <StudentEmptyState hasSearch={!!debouncedSearch} />
      ) : (
        <StudentTable
          rows={filtered}
          studentsById={studentsById}
          onEdit={handleEdit}
          onDelete={handleDeleteClick}
        />
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
