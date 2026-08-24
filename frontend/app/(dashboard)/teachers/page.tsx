"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useUserStore, useRoles } from "@/store/user-store";
import { useDebounce } from "@/hooks/use-debounce";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  useTeachers,
  useTeachersWithStats,
  useCreateTeacher,
  useUpdateTeacher,
  useDeleteTeacher,
  useBulkDeleteTeachers,
  useSubjectOptions,
  useTeacherSubjects,
  useSetTeacherSubjects,
} from "./_hooks/use-teachers";
import type {
  TeacherCreate,
  TeacherResponse,
  TeacherUpdate,
  TeacherWithStats,
} from "./_schemas/teacher";
import { TeacherTable } from "./_components/teacher-table";
import { TeacherBulkActionBar } from "./_components/teacher-bulk-action-bar";
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
  // Delete is Manager-only (RBAC); hide the controls for others.
  const { isManager } = useRoles();

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);

  const [editTarget, setEditTarget] = useState<TeacherResponse | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<TeacherResponse | null>(
    null
  );
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);

  const teachersQuery = useTeachers(branchId);
  const statsQuery = useTeachersWithStats(branchId);
  const createMutation = useCreateTeacher(branchId);
  const updateMutation = useUpdateTeacher(branchId);
  const deleteMutation = useDeleteTeacher(branchId);
  const bulkDeleteMutation = useBulkDeleteTeachers(branchId);
  const subjectOptionsQuery = useSubjectOptions(branchId);
  const editSubjectsQuery = useTeacherSubjects(branchId, editTarget?.id);
  const setSubjectsMutation = useSetTeacherSubjects(branchId);

  const subjectOptions = subjectOptionsQuery.data ?? [];

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

  async function handleUpdate(data: TeacherUpdate, subjects: string[]) {
    if (!editTarget) return;
    await updateMutation.mutateAsync({ teacherId: editTarget.id, data });
    await setSubjectsMutation.mutateAsync({
      teacherId: editTarget.id,
      subjects,
    });
  }

  function handleDeleteClick(teacher: TeacherResponse) {
    setDeleteTarget(teacher);
  }

  async function handleDeleteConfirm() {
    if (!deleteTarget) return;
    await deleteMutation.mutateAsync(deleteTarget.id);
  }

  // --- Selection + bulk delete ---
  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // Operates on the currently filtered rows (filtering is client-side here).
  function toggleSelectAll() {
    setSelectedIds((prev) => {
      const allOnPage = filtered.every((r) => prev.has(r.id));
      const next = new Set(prev);
      if (allOnPage) filtered.forEach((r) => next.delete(r.id));
      else filtered.forEach((r) => next.add(r.id));
      return next;
    });
  }

  function clearSelection() {
    setSelectedIds(new Set());
  }

  async function handleBulkDeleteConfirm() {
    if (selectedIds.size === 0) return;
    await bulkDeleteMutation.mutateAsync([...selectedIds]);
    clearSelection();
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Teachers"
        description="Manage faculty for your branch."
        actions={
          <>
            <Button
              variant="secondary"
              size="sm"
              render={<Link href="/teachers/productivity" />}
            >
              Productivity report
            </Button>
            {branchId && <ImportTeachersDialog branchId={branchId} />}
            <CreateTeacherDialog
              onSubmit={handleCreate}
              isPending={createMutation.isPending}
              subjectOptions={subjectOptions}
            />
          </>
        }
      />

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
        <>
          {selectedIds.size > 0 && isManager && (
            <TeacherBulkActionBar
              count={selectedIds.size}
              pending={bulkDeleteMutation.isPending}
              onDelete={() => setBulkDeleteOpen(true)}
              onClear={clearSelection}
            />
          )}
          <TeacherTable
            rows={filtered}
            teachersById={teachersById}
            onEdit={handleEdit}
            onDelete={isManager ? handleDeleteClick : undefined}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelect}
            onToggleSelectAll={toggleSelectAll}
          />
        </>
      )}

      <EditTeacherDialog
        teacher={editTarget}
        open={editOpen}
        onOpenChange={setEditOpen}
        onSubmit={handleUpdate}
        isPending={updateMutation.isPending || setSubjectsMutation.isPending}
        subjectOptions={subjectOptions}
        currentSubjects={editSubjectsQuery.data ?? []}
        subjectsLoading={editSubjectsQuery.isLoading}
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

      <ConfirmDialog
        open={bulkDeleteOpen}
        onOpenChange={setBulkDeleteOpen}
        title={`Delete ${selectedIds.size} teacher(s)?`}
        description={`This soft-deletes the ${selectedIds.size} selected teacher(s) and removes their subject/batch assignments. They can be restored by re-importing.`}
        confirmLabel="Delete selected"
        destructive
        onConfirm={handleBulkDeleteConfirm}
      />
    </div>
  );
}
