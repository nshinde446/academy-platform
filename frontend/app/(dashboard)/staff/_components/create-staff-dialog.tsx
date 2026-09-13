"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogTrigger,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { apiErrorMessage } from "@/lib/api-error";
import type { DepartmentWithAllocation, StaffCreate } from "../_schemas/staff";

interface CreateStaffDialogProps {
  departments: DepartmentWithAllocation[];
  onSubmit: (data: Omit<StaffCreate, "branch_id">) => Promise<void> | void;
  isPending: boolean;
}

const EMPTY = {
  first_name: "",
  last_name: "",
  title: "",
  designation: "",
  email: "",
  phone: "",
  emp_code: "",
};

export function CreateStaffDialog({
  departments,
  onSubmit,
  isPending,
}: CreateStaffDialogProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [deptId, setDeptId] = useState("");
  const [error, setError] = useState("");

  const dept = departments.find((d) => d.id === deptId);

  function reset() {
    setForm(EMPTY);
    setDeptId("");
    setError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.first_name) return setError("First name is required");
    if (!deptId) return setError("Department is required");
    try {
      await onSubmit({
        first_name: form.first_name,
        last_name: form.last_name || "",
        title: form.title || undefined,
        department_id: deptId,
        designation: form.designation || undefined,
        email: form.email || undefined,
        phone: form.phone || undefined,
        emp_code: form.emp_code.trim() || undefined,
      });
      reset();
      setOpen(false);
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to create staff"));
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger
        render={<Button onClick={() => setOpen(true)}>Add Staff</Button>}
      />
      <DialogPopup>
        <DialogTitle>Add Staff</DialogTitle>
        <DialogDescription>
          Add a staff member. An employee code is auto-allocated from the
          department&apos;s reserved range unless you set one.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="s_title">Title</Label>
              <Input
                id="s_title"
                value={form.title}
                placeholder="Mr / Mrs"
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="s_first">First Name *</Label>
              <Input
                id="s_first"
                value={form.first_name}
                onChange={(e) =>
                  setForm({ ...form, first_name: e.target.value })
                }
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="s_last">Last Name</Label>
              <Input
                id="s_last"
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="s_dept">Department *</Label>
              <select
                id="s_dept"
                value={deptId}
                onChange={(e) => setDeptId(e.target.value)}
                required
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="">Select…</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.id_range_start}–{d.id_range_end})
                  </option>
                ))}
              </select>
              {dept && (
                <p className="text-xs text-muted-foreground">
                  {dept.next_emp_code
                    ? `Next code: ${dept.next_emp_code} (${dept.used} used)`
                    : "Range is full — set a code manually"}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="s_designation">Designation</Label>
              <Input
                id="s_designation"
                value={form.designation}
                placeholder="e.g. Teacher, Accounts Head"
                onChange={(e) =>
                  setForm({ ...form, designation: e.target.value })
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="s_emp">Employee code</Label>
              <Input
                id="s_emp"
                value={form.emp_code}
                placeholder={dept?.next_emp_code ?? "auto"}
                onChange={(e) => setForm({ ...form, emp_code: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="s_email">Email</Label>
              <Input
                id="s_email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="s_phone">Phone</Label>
              <Input
                id="s_phone"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  Cancel
                </Button>
              }
            />
            <Button type="submit" disabled={isPending}>
              {isPending ? "Adding…" : "Add"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
