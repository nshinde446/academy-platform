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
  useCourses,
  useCreateCourse,
  useDeleteCourse,
  useUpdateCourse,
} from "./_hooks/use-courses";
import type {
  CourseCreate,
  CourseResponse,
  CourseUpdate,
} from "./_schemas/course";
import { CourseTable } from "./_components/course-table";
import { CourseEmptyState } from "./_components/course-empty-state";
import { CreateCourseDialog } from "./_components/create-course-dialog";
import { EditCourseDialog } from "./_components/edit-course-dialog";
import { ManageSubjectsDialog } from "./_components/manage-subjects-dialog";

function filterCourses(
  courses: CourseResponse[],
  query: string
): CourseResponse[] {
  if (!query) return courses;
  const q = query.toLowerCase();
  return courses.filter(
    (c) =>
      c.name.toLowerCase().includes(q) ||
      c.code.toLowerCase().includes(q) ||
      c.description?.toLowerCase().includes(q)
  );
}

export default function CoursesPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);

  const [editTarget, setEditTarget] = useState<CourseResponse | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<CourseResponse | null>(null);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [manageTarget, setManageTarget] = useState<CourseResponse | null>(null);
  const [manageOpen, setManageOpen] = useState(false);

  const toast = useToast();
  const selection = useRowSelection();

  const coursesQuery = useCourses(branchId);
  const createMutation = useCreateCourse(branchId);
  const updateMutation = useUpdateCourse(branchId);
  const deleteMutation = useDeleteCourse(branchId);

  const filtered = useMemo(
    () => filterCourses(coursesQuery.data ?? [], debouncedSearch),
    [coursesQuery.data, debouncedSearch]
  );

  async function handleCreate(data: Omit<CourseCreate, "branch_id">) {
    if (!branchId) return;
    await createMutation.mutateAsync({ ...data, branch_id: branchId });
  }

  function handleEdit(course: CourseResponse) {
    setEditTarget(course);
    setEditOpen(true);
  }

  async function handleUpdate(data: CourseUpdate) {
    if (!editTarget) return;
    await updateMutation.mutateAsync({ courseId: editTarget.id, data });
  }

  function handleDeleteClick(course: CourseResponse) {
    setDeleteTarget(course);
  }

  function handleManageSubjects(course: CourseResponse) {
    setManageTarget(course);
    setManageOpen(true);
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
    const summary = summarizeBulkDelete(result, "course");
    if (result.failed.length > 0) toast.info("Bulk delete", summary);
    else toast.success("Bulk delete", summary);
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Courses"
        description="Master course definitions (NEET, JEE, Class 9, etc.) used across academic years."
        actions={
          <CreateCourseDialog
            onSubmit={handleCreate}
            isPending={createMutation.isPending}
          />
        }
      />

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="Search by name, code, or description..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:max-w-sm"
        />
        <span className="text-sm text-muted-foreground">
          {filtered.length} course{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      <SelectionBar
        count={selection.count}
        noun="course"
        pending={deleteMutation.isPending}
        onDelete={() => setBulkDeleteOpen(true)}
        onClear={selection.clear}
      />

      {/* Content */}
      {coursesQuery.isLoading ? (
        <p className="text-muted-foreground text-sm">Loading courses...</p>
      ) : coursesQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to load courses. Make sure the backend is running.
        </p>
      ) : filtered.length === 0 ? (
        <CourseEmptyState hasSearch={!!debouncedSearch} />
      ) : (
        <CourseTable
          courses={filtered}
          onEdit={handleEdit}
          onDelete={handleDeleteClick}
          onManageSubjects={handleManageSubjects}
          selectedIds={selection.selectedIds}
          onToggleSelect={selection.toggle}
          onToggleSelectAll={() => selection.toggleAll(filtered.map((c) => c.id))}
        />
      )}

      <ManageSubjectsDialog
        course={manageTarget}
        open={manageOpen}
        onOpenChange={setManageOpen}
        branchId={branchId}
      />

      <EditCourseDialog
        course={editTarget}
        open={editOpen}
        onOpenChange={setEditOpen}
        onSubmit={handleUpdate}
        isPending={updateMutation.isPending}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title="Delete course?"
        description={
          deleteTarget
            ? `Are you sure you want to delete "${deleteTarget.name}"? This cannot be undone. Courses with active batches cannot be deleted.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteConfirm}
      />

      <ConfirmDialog
        open={bulkDeleteOpen}
        onOpenChange={setBulkDeleteOpen}
        title={`Delete ${selection.count} course${selection.count !== 1 ? "s" : ""}?`}
        description="This cannot be undone. Courses with active batches are skipped and reported."
        confirmLabel={`Delete ${selection.count}`}
        destructive
        onConfirm={handleBulkDeleteConfirm}
      />
    </div>
  );
}
