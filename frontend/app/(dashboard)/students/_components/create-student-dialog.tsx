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
import type {
  AcademicYearResponse,
  Standard,
  StudentCreate,
  TargetExam,
} from "../_schemas/student";
import { STANDARDS, TARGET_EXAMS } from "../_schemas/student";

interface CreateStudentDialogProps {
  academicYears: AcademicYearResponse[];
  onSubmit: (data: Omit<StudentCreate, "branch_id">) => Promise<void> | void;
  isPending: boolean;
}

const EMPTY_FORM = {
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  date_of_birth: "",
  enrollment_number: "",
  parent_mobile: "",
  rfid_number: "",
  gender: "",
  standard: "" as Standard | "",
  target_exam: "" as TargetExam | "",
};

export function CreateStudentDialog({
  academicYears,
  onSubmit,
  isPending,
}: CreateStudentDialogProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState("");

  function reset() {
    setForm(EMPTY_FORM);
    setError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.first_name || !form.last_name) {
      setError("First name and last name are required");
      return;
    }
    if (!form.standard) {
      setError("Pick the student's standard / class");
      return;
    }
    if (!form.target_exam) {
      setError("Pick the student's target exam");
      return;
    }
    const yearId = academicYears[0]?.id;
    if (!yearId) {
      setError("No academic year available. Create one first via the API.");
      return;
    }

    try {
      await onSubmit({
        academic_year_id: yearId,
        first_name: form.first_name,
        last_name: form.last_name,
        standard: form.standard as Standard,
        target_exam: form.target_exam as TargetExam,
        email: form.email || undefined,
        phone: form.phone || undefined,
        date_of_birth: form.date_of_birth || undefined,
        enrollment_number: form.enrollment_number || undefined,
        parent_mobile: form.parent_mobile || undefined,
        rfid_number: form.rfid_number || undefined,
        gender: form.gender || undefined,
      });
      reset();
      setOpen(false);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Failed to create student");
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        setOpen(isOpen);
        if (!isOpen) reset();
      }}
    >
      <DialogTrigger
        render={<Button onClick={() => setOpen(true)}>Create Student</Button>}
      />
      <DialogPopup>
        <DialogTitle>Create Student</DialogTitle>
        <DialogDescription>Add a new student to this branch.</DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          {academicYears.length > 1 && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="academic_year">Academic Year</Label>
              <select
                id="academic_year"
                className="flex h-8 w-full rounded-lg border border-input bg-background px-3 text-sm"
                defaultValue={academicYears[0]?.id}
              >
                {academicYears.map((ay) => (
                  <option key={ay.id} value={ay.id}>
                    {ay.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="first_name">First Name *</Label>
              <Input
                id="first_name"
                value={form.first_name}
                onChange={(e) =>
                  setForm({ ...form, first_name: e.target.value })
                }
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="last_name">Last Name *</Label>
              <Input
                id="last_name"
                value={form.last_name}
                onChange={(e) =>
                  setForm({ ...form, last_name: e.target.value })
                }
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="create_email">Email</Label>
              <Input
                id="create_email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="create_phone">Phone</Label>
              <Input
                id="create_phone"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="enrollment_number">Roll No</Label>
              <Input
                id="enrollment_number"
                value={form.enrollment_number}
                onChange={(e) =>
                  setForm({ ...form, enrollment_number: e.target.value })
                }
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="date_of_birth">Date of Birth</Label>
              <Input
                id="date_of_birth"
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
              <Label htmlFor="parent_mobile">Parent Mobile</Label>
              <Input
                id="parent_mobile"
                value={form.parent_mobile}
                onChange={(e) =>
                  setForm({ ...form, parent_mobile: e.target.value })
                }
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rfid_number">RFID Number</Label>
              <Input
                id="rfid_number"
                value={form.rfid_number}
                onChange={(e) =>
                  setForm({ ...form, rfid_number: e.target.value })
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="create_standard">Standard *</Label>
              <select
                id="create_standard"
                value={form.standard}
                onChange={(e) =>
                  setForm({ ...form, standard: e.target.value as Standard })
                }
                className="flex h-8 w-full rounded-lg border border-input bg-background px-3 text-sm"
                required
              >
                <option value="">Pick standard…</option>
                {STANDARDS.map((s) => (
                  <option key={s} value={s}>
                    {s === "Dropper" ? "Dropper" : `Class ${s}`}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="create_target_exam">Target exam *</Label>
              <select
                id="create_target_exam"
                value={form.target_exam}
                onChange={(e) =>
                  setForm({
                    ...form,
                    target_exam: e.target.value as TargetExam,
                  })
                }
                className="flex h-8 w-full rounded-lg border border-input bg-background px-3 text-sm"
                required
              >
                <option value="">Pick target exam…</option>
                {TARGET_EXAMS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5 sm:max-w-[calc(50%-0.375rem)]">
            <Label htmlFor="gender">Gender</Label>
            <select
              id="gender"
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
              {isPending ? "Creating..." : "Create"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
