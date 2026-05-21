"use client";

import { useMemo, useState } from "react";
import { useUserStore } from "@/store/user-store";
import { useDebounce } from "@/hooks/use-debounce";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  useClassrooms,
  useCreateClassroom,
  useUpdateClassroom,
  useDeleteClassroom,
} from "./_hooks/use-classrooms";
import type {
  ClassroomCreate,
  ClassroomResponse,
  ClassroomUpdate,
} from "./_schemas/classroom";
import { ClassroomTable } from "./_components/classroom-table";
import { ClassroomEmptyState } from "./_components/classroom-empty-state";
import { CreateClassroomDialog } from "./_components/create-classroom-dialog";
import { EditClassroomDialog } from "./_components/edit-classroom-dialog";

function filterClassrooms(
  classrooms: ClassroomResponse[],
  query: string
): ClassroomResponse[] {
  if (!query) return classrooms;
  const q = query.toLowerCase();
  return classrooms.filter(
    (c) =>
      c.name.toLowerCase().includes(q) ||
      c.code.toLowerCase().includes(q) ||
      c.floor?.toLowerCase().includes(q)
  );
}

export default function ClassroomsPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);

  const [editTarget, setEditTarget] = useState<ClassroomResponse | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ClassroomResponse | null>(
    null
  );

  const classroomsQuery = useClassrooms(branchId);
  const createMutation = useCreateClassroom(branchId);
  const updateMutation = useUpdateClassroom(branchId);
  const deleteMutation = useDeleteClassroom(branchId);

  const filtered = useMemo(
    () => filterClassrooms(classroomsQuery.data ?? [], debouncedSearch),
    [classroomsQuery.data, debouncedSearch]
  );

  async function handleCreate(data: Omit<ClassroomCreate, "branch_id">) {
    if (!branchId) return;
    await createMutation.mutateAsync({ ...data, branch_id: branchId });
  }

  function handleEdit(c: ClassroomResponse) {
    setEditTarget(c);
    setEditOpen(true);
  }

  async function handleUpdate(data: ClassroomUpdate) {
    if (!editTarget) return;
    await updateMutation.mutateAsync({ classroomId: editTarget.id, data });
  }

  function handleDeleteClick(c: ClassroomResponse) {
    setDeleteTarget(c);
  }

  async function handleDeleteConfirm() {
    if (!deleteTarget) return;
    await deleteMutation.mutateAsync(deleteTarget.id);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Classrooms</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage physical rooms for offline / hybrid lectures
          </p>
        </div>
        <CreateClassroomDialog
          onSubmit={handleCreate}
          isPending={createMutation.isPending}
        />
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="Search by name, code, or floor..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:max-w-sm"
        />
        <span className="text-sm text-muted-foreground">
          {filtered.length} classroom{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {classroomsQuery.isLoading ? (
        <p className="text-muted-foreground text-sm">Loading classrooms...</p>
      ) : classroomsQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to load classrooms. Make sure the backend is running.
        </p>
      ) : filtered.length === 0 ? (
        <ClassroomEmptyState hasSearch={!!debouncedSearch} />
      ) : (
        <ClassroomTable
          classrooms={filtered}
          onEdit={handleEdit}
          onDelete={handleDeleteClick}
        />
      )}

      <EditClassroomDialog
        classroom={editTarget}
        open={editOpen}
        onOpenChange={setEditOpen}
        onSubmit={handleUpdate}
        isPending={updateMutation.isPending}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title="Delete classroom?"
        description={
          deleteTarget
            ? `Are you sure you want to delete "${deleteTarget.name}"? Lectures already booked in this room will keep their reference.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
