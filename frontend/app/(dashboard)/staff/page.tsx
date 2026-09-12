"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useUserStore, useRoles } from "@/store/user-store";
import { useDebounce } from "@/hooks/use-debounce";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { SelectionBar } from "@/components/ui/selection-bar";
import {
  useStaff,
  useDepartments,
  useCreateStaff,
  useUpdateStaff,
  useDeleteStaff,
  useBulkDeleteStaff,
} from "./_hooks/use-staff";
import type { StaffCreate, StaffResponse, StaffUpdate } from "./_schemas/staff";
import { StaffTable } from "./_components/staff-table";
import { CreateStaffDialog } from "./_components/create-staff-dialog";
import { EditStaffDialog } from "./_components/edit-staff-dialog";
import { ImportStaffDialog } from "./_components/import-staff-dialog";

function filterStaff(rows: StaffResponse[], q: string): StaffResponse[] {
  if (!q) return rows;
  const s = q.toLowerCase();
  return rows.filter(
    (r) =>
      `${r.first_name} ${r.last_name}`.toLowerCase().includes(s) ||
      r.emp_code.toLowerCase().includes(s) ||
      r.designation?.toLowerCase().includes(s) ||
      r.department_name?.toLowerCase().includes(s)
  );
}

export default function StaffPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;
  const { isManager } = useRoles();

  const [search, setSearch] = useState("");
  const debounced = useDebounce(search, 300);
  const [deptFilter, setDeptFilter] = useState("");

  const [editTarget, setEditTarget] = useState<StaffResponse | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<StaffResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkOpen, setBulkOpen] = useState(false);

  const departmentsQuery = useDepartments(branchId);
  const staffQuery = useStaff(branchId, deptFilter || undefined);
  const createMutation = useCreateStaff(branchId);
  const updateMutation = useUpdateStaff(branchId);
  const deleteMutation = useDeleteStaff(branchId);
  const bulkDeleteMutation = useBulkDeleteStaff(branchId);

  const departments = departmentsQuery.data ?? [];
  const filtered = useMemo(
    () => filterStaff(staffQuery.data ?? [], debounced),
    [staffQuery.data, debounced]
  );

  async function handleCreate(data: Omit<StaffCreate, "branch_id">) {
    if (!branchId) return;
    await createMutation.mutateAsync({ ...data, branch_id: branchId });
  }

  async function handleUpdate(data: StaffUpdate) {
    if (!editTarget) return;
    await updateMutation.mutateAsync({ id: editTarget.id, data });
  }

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
      const all = filtered.every((r) => prev.has(r.id));
      const next = new Set(prev);
      filtered.forEach((r) => (all ? next.delete(r.id) : next.add(r.id)));
      return next;
    });
  }
  function clearSelection() {
    setSelectedIds(new Set());
  }
  async function handleBulkDelete() {
    if (selectedIds.size === 0) return;
    await bulkDeleteMutation.mutateAsync([...selectedIds]);
    clearSelection();
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Staff"
        description="Department-wise staff with reserved employee-code ranges."
        actions={
          <>
            <Button
              variant="secondary"
              size="sm"
              render={<Link href="/staff/reports" />}
            >
              Reports
            </Button>
            {branchId && <ImportStaffDialog branchId={branchId} />}
            <CreateStaffDialog
              departments={departments}
              onSubmit={handleCreate}
              isPending={createMutation.isPending}
            />
          </>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="Search by name, code, designation…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:max-w-sm"
        />
        <select
          value={deptFilter}
          onChange={(e) => setDeptFilter(e.target.value)}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
        >
          <option value="">All departments</option>
          {departments.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <span className="text-sm text-muted-foreground">
          {filtered.length} staff
        </span>
      </div>

      {staffQuery.isLoading ? (
        <p className="text-muted-foreground text-sm">Loading staff…</p>
      ) : staffQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to load staff. Make sure the backend is running.
        </p>
      ) : filtered.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No staff yet. Add one or import the roster.
        </p>
      ) : (
        <>
          {isManager && (
            <SelectionBar
              count={selectedIds.size}
              noun="staff"
              pending={bulkDeleteMutation.isPending}
              onDelete={() => setBulkOpen(true)}
              onClear={clearSelection}
            />
          )}
          <StaffTable
            rows={filtered}
            onEdit={(s) => {
              setEditTarget(s);
              setEditOpen(true);
            }}
            onDelete={isManager ? (s) => setDeleteTarget(s) : undefined}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelect}
            onToggleSelectAll={toggleSelectAll}
          />
        </>
      )}

      <EditStaffDialog
        key={editTarget?.id ?? "none"}
        staff={editTarget}
        open={editOpen}
        onOpenChange={setEditOpen}
        departments={departments}
        onSubmit={handleUpdate}
        isPending={updateMutation.isPending}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title="Delete staff?"
        description={
          deleteTarget
            ? `Delete "${deleteTarget.first_name} ${deleteTarget.last_name}" (${deleteTarget.emp_code})? This can be restored by re-importing.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        onConfirm={async () => {
          if (deleteTarget) await deleteMutation.mutateAsync(deleteTarget.id);
        }}
      />

      <ConfirmDialog
        open={bulkOpen}
        onOpenChange={setBulkOpen}
        title={`Delete ${selectedIds.size} staff?`}
        description={`This soft-deletes the ${selectedIds.size} selected staff member(s).`}
        confirmLabel="Delete selected"
        destructive
        onConfirm={handleBulkDelete}
      />
    </div>
  );
}
