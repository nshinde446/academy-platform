"use client";

import { useMemo, useState } from "react";
import { useUserStore } from "@/store/user-store";
import { useDebounce } from "@/hooks/use-debounce";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  useTeachers,
  useTeachersWithStats,
  useCreateTeacher,
  useUpdateTeacher,
  useDeleteTeacher,
} from "./_hooks/use-teachers";
import type {
  TeacherCreate,
  TeacherResponse,
  TeacherUpdate,
  TeacherWithStats,
} from "./_schemas/teacher";
import { TeacherTable } from "./_components/teacher-table";
import { TeacherEmptyState } from "./_components/teacher-empty-state";
import { CreateTeacherDialog } from "./_components/create-teacher-dialog";
import { EditTeacherDialog } from "./_components/edit-teacher-dialog";
import { ImportTeachersDialog } from "./_components/import-teachers-dialog";

function filterTeachers(
  rows: TeacherWithStats[],
  query: string
): TeacherWithStats[] {
  if (!query) return rows;
  const q = query.toLowerCase();
  return rows.filter(
    (t) =>
      `${t.first_name} ${t.last_name}`.toLowerCase().includes(q) ||
      t.qualification?.toLowerCase().includes(q) ||
      t.subject_name?.toLowerCase().includes(q),
  );
}

export default function TeachersPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);

  const [editTarget, setEditTarget] = useState<TeacherResponse | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<TeacherResponse | null>(
    null
  );

  const teachersQuery = useTeachers(branchId);
  const statsQuery = useTeachersWithStats(branchId);
  const createMutation = useCreateTeacher(branchId);
  const updateMutation = useUpdateTeacher(branchId);
  const deleteMutation = useDeleteTeacher(branchId);

  const teachersById = useMemo(() => {
    const map: Record<string, TeacherResponse> = {};
    for (const t of teachersQuery.data ?? []) map[t.id] = t;
    return map;
  }, [teachersQuery.data]);

  const filtered = useMemo(
    () => filterTeachers(statsQuery.data ?? [], debouncedSearch),
    [statsQuery.data, debouncedSearch]
  );

  async function handleCreate(data: Omit<TeacherCreate, "branch_id">) {
    if (!branchId) return;
    await createMutation.mutateAsync({ ...data, branch_id: branchId });
  }

  function handleEdit(teacher: TeacherResponse) {
    setEditTarget(teacher);
    setEditOpen(true);
  }

  async function handleUpdate(data: TeacherUpdate) {
    if (!editTarget) return;
    await updateMutation.mutateAsync({ teacherId: editTarget.id, data });
  }

  function handleDeleteClick(teacher: TeacherResponse) {
    setDeleteTarget(teacher);
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
          <h2 className="text-2xl font-semibold">Teachers</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage faculty for your branch
          </p>
        </div>
        <div className="flex gap-2">
          {branchId && <ImportTeachersDialog branchId={branchId} />}
          <CreateTeacherDialog
            onSubmit={handleCreate}
            isPending={createMutation.isPending}
          />
        </div>
      </div>

      {/* Search */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="Search by name, email, or qualification..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:max-w-sm"
        />
        <span className="text-sm text-muted-foreground">
          {filtered.length} teacher{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Content */}
      {statsQuery.isLoading || teachersQuery.isLoading ? (
        <p className="text-muted-foreground text-sm">Loading teachers...</p>
      ) : statsQuery.isError || teachersQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to load teachers. Make sure the backend is running.
        </p>
      ) : filtered.length === 0 ? (
        <TeacherEmptyState hasSearch={!!debouncedSearch} />
      ) : (
        <TeacherTable
          rows={filtered}
          teachersById={teachersById}
          onEdit={handleEdit}
          onDelete={handleDeleteClick}
        />
      )}

      <EditTeacherDialog
        teacher={editTarget}
        open={editOpen}
        onOpenChange={setEditOpen}
        onSubmit={handleUpdate}
        isPending={updateMutation.isPending}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title="Delete teacher?"
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
