"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { apiErrorMessage } from "@/lib/api-error";
import type {
  DepartmentWithAllocation,
  StaffResponse,
  StaffUpdate,
} from "../_schemas/staff";

interface EditStaffDialogProps {
  staff: StaffResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  departments: DepartmentWithAllocation[];
  onSubmit: (data: StaffUpdate) => Promise<void> | void;
  isPending: boolean;
}

export function EditStaffDialog({
  staff,
  open,
  onOpenChange,
  departments,
  onSubmit,
  isPending,
}: EditStaffDialogProps) {
  // Initialise straight from the staff prop. The parent gives this dialog a
  // `key={staff.id}` so it remounts (fresh state) when a different row is
  // edited — no set-state-in-effect needed.
  const [form, setForm] = useState<StaffUpdate>(() => ({
    title: staff?.title ?? "",
    first_name: staff?.first_name ?? "",
    last_name: staff?.last_name ?? "",
    department_id: staff?.department_id ?? "",
    designation: staff?.designation ?? "",
    emp_code: staff?.emp_code ?? "",
    email: staff?.email ?? "",
    phone: staff?.phone ?? "",
    shift_start: staff?.shift_start ?? "",
    shift_end: staff?.shift_end ?? "",
    weekly_off_days: staff?.weekly_off_days ?? "",
  }));
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await onSubmit(form);
      onOpenChange(false);
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to update staff"));
    }
  }

  function set<K extends keyof StaffUpdate>(k: K, v: StaffUpdate[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>Edit Staff</DialogTitle>
        <DialogDescription>
          Update details, employee code, department, or shift.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="e_title">Title</Label>
              <Input
                id="e_title"
                value={form.title ?? ""}
                onChange={(e) => set("title", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="e_first">First Name</Label>
              <Input
                id="e_first"
                value={form.first_name ?? ""}
                onChange={(e) => set("first_name", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="e_last">Last Name</Label>
              <Input
                id="e_last"
                value={form.last_name ?? ""}
                onChange={(e) => set("last_name", e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="e_dept">Department</Label>
              <select
                id="e_dept"
                value={form.department_id ?? ""}
                onChange={(e) => set("department_id", e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="e_emp">Employee code</Label>
              <Input
                id="e_emp"
                value={form.emp_code ?? ""}
                onChange={(e) => set("emp_code", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="e_designation">Designation</Label>
              <Input
                id="e_designation"
                value={form.designation ?? ""}
                onChange={(e) => set("designation", e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="e_shift_start">Shift start</Label>
              <Input
                id="e_shift_start"
                placeholder="10:00"
                value={form.shift_start ?? ""}
                onChange={(e) => set("shift_start", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="e_shift_end">Shift end</Label>
              <Input
                id="e_shift_end"
                placeholder="20:00"
                value={form.shift_end ?? ""}
                onChange={(e) => set("shift_end", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="e_email">Email</Label>
              <Input
                id="e_email"
                value={form.email ?? ""}
                onChange={(e) => set("email", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="e_phone">Phone</Label>
              <Input
                id="e_phone"
                value={form.phone ?? ""}
                onChange={(e) => set("phone", e.target.value)}
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
              {isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
