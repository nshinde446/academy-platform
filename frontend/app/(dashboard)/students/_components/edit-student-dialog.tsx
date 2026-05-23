"use client";

import { useEffect, useState } from "react";
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
import type {
  Standard,
  StudentResponse,
  StudentUpdate,
  TargetExam,
} from "../_schemas/student";
import { STANDARDS, TARGET_EXAMS } from "../_schemas/student";

interface EditStudentDialogProps {
  student: StudentResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: StudentUpdate) => Promise<void> | void;
  isPending: boolean;
}

function buildForm(s: StudentResponse | null) {
  return {
    first_name: s?.first_name ?? "",
    last_name: s?.last_name ?? "",
    email: s?.email ?? "",
    phone: s?.phone ?? "",
    date_of_birth: s?.date_of_birth ?? "",
    enrollment_number: s?.enrollment_number ?? "",
    parent_mobile: s?.parent_mobile ?? "",
    rfid_number: s?.rfid_number ?? "",
    gender: s?.gender ?? "",
    standard: (s?.standard ?? "") as Standard | "",
    target_exam: (s?.target_exam ?? "") as TargetExam | "",
  };
}

export function EditStudentDialog({
  student,
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: EditStudentDialogProps) {
  const [form, setForm] = useState(() => buildForm(student));
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setForm(buildForm(student));
      setError("");
    }
  }, [open, student]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.first_name) {
      setError("First name is required");
      return;
    }
    try {
      await onSubmit({
        first_name: form.first_name,
        last_name: form.last_name || null,
        email: form.email || null,
        phone: form.phone || null,
        date_of_birth: form.date_of_birth || null,
        enrollment_number: form.enrollment_number || null,
        parent_mobile: form.parent_mobile || null,
        rfid_number: form.rfid_number || null,
        gender: form.gender || null,
        standard: form.standard || null,
        target_exam: form.target_exam || null,
      });
      onOpenChange(false);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Failed to update student");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>Edit Student</DialogTitle>
        <DialogDescription>
          Update the fields and save.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit_first_name">First Name *</Label>
              <Input
                id="edit_first_name"
                value={form.first_name}
                onChange={(e) =>
                  setForm({ ...form, first_name: e.target.value })
                }
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit_last_name">Last Name</Label>
              <Input
                id="edit_last_name"
                value={form.last_name}
                onChange={(e) =>
                  setForm({ ...form, last_name: e.target.value })
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit_email">Email</Label>
              <Input
                id="edit_email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit_phone">Phone</Label>
              <Input
                id="edit_phone"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit_enrollment">Roll No</Label>
              <Input
                id="edit_enrollment"
                value={form.enrollment_number}
                onChange={(e) =>
                  setForm({ ...form, enrollment_number: e.target.value })
                }
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit_dob">Date of Birth</Label>
              <Input
                id="edit_dob"
                type="date"
                value={form.date_of_birth}
                onChange={(e) =>
                  setForm({ ...form, date_of_birth: e.target.value })
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit_parent_mobile">Parent Mobile</Label>
              <Input
                id="edit_parent_mobile"
                value={form.parent_mobile}
                onChange={(e) =>
                  setForm({ ...form, parent_mobile: e.target.value })
                }
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit_rfid">RFID Number</Label>
              <Input
                id="edit_rfid"
                value={form.rfid_number}
                onChange={(e) =>
                  setForm({ ...form, rfid_number: e.target.value })
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit_standard">Standard</Label>
              <select
                id="edit_standard"
                value={form.standard}
                onChange={(e) =>
                  setForm({ ...form, standard: e.target.value as Standard })
                }
                className="flex h-8 w-full rounded-lg border border-input bg-background px-3 text-sm"
              >
                <option value="">—</option>
                {STANDARDS.map((s) => (
                  <option key={s} value={s}>
                    {s === "Dropper" ? "Dropper" : `Class ${s}`}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit_target_exam">Target exam</Label>
              <select
                id="edit_target_exam"
                value={form.target_exam}
                onChange={(e) =>
                  setForm({
                    ...form,
                    target_exam: e.target.value as TargetExam,
                  })
                }
                className="flex h-8 w-full rounded-lg border border-input bg-background px-3 text-sm"
              >
                <option value="">—</option>
                {TARGET_EXAMS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5 sm:max-w-[calc(50%-0.375rem)]">
            <Label htmlFor="edit_gender">Gender</Label>
            <select
              id="edit_gender"
              value={form.gender}
              onChange={(e) => setForm({ ...form, gender: e.target.value })}
              className="flex h-8 w-full rounded-lg border border-input bg-background px-3 text-sm"
            >
              <option value="">—</option>
              <option value="M">Male</option>
              <option value="F">Female</option>
              <option value="Other">Other</option>
            </select>
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
              {isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
