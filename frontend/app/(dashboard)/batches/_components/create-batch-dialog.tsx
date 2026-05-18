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
  BatchCreate,
  CourseResponse,
} from "../_schemas/batch";

interface CreateBatchDialogProps {
  academicYears: AcademicYearResponse[];
  courses: CourseResponse[];
  onSubmit: (data: Omit<BatchCreate, "branch_id">) => Promise<void> | void;
  isPending: boolean;
}

const EMPTY_FORM = {
  name: "",
  code: "",
  capacity: "30",
};

export function CreateBatchDialog({
  academicYears,
  courses,
  onSubmit,
  isPending,
}: CreateBatchDialogProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [selectedCourse, setSelectedCourse] = useState("");
  const [error, setError] = useState("");

  function reset() {
    setForm(EMPTY_FORM);
    setSelectedCourse("");
    setError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name || !form.code) {
      setError("Batch name and code are required");
      return;
    }
    const yearId = academicYears[0]?.id;
    if (!yearId) {
      setError("No academic year available. Create one first.");
      return;
    }
    const courseId = selectedCourse || courses[0]?.id;
    if (!courseId) {
      setError("No course available. Create a course first.");
      return;
    }

    try {
      await onSubmit({
        academic_year_id: yearId,
        course_id: courseId,
        name: form.name,
        code: form.code,
        capacity: parseInt(form.capacity, 10) || 30,
      });
      reset();
      setOpen(false);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Failed to create batch");
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
        render={<Button onClick={() => setOpen(true)}>Create Batch</Button>}
      />
      <DialogPopup>
        <DialogTitle>Create Batch</DialogTitle>
        <DialogDescription>Add a new batch to this branch.</DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          {courses.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="batch_course">Course</Label>
              <select
                id="batch_course"
                value={selectedCourse || courses[0]?.id || ""}
                onChange={(e) => setSelectedCourse(e.target.value)}
                className="flex h-8 w-full rounded-lg border border-input bg-background px-3 text-sm"
              >
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.code})
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="batch_name">Batch Name *</Label>
              <Input
                id="batch_name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="batch_code">Batch Code *</Label>
              <Input
                id="batch_code"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5 sm:max-w-[calc(50%-0.375rem)]">
            <Label htmlFor="batch_capacity">Capacity</Label>
            <Input
              id="batch_capacity"
              type="number"
              min={1}
              value={form.capacity}
              onChange={(e) => setForm({ ...form, capacity: e.target.value })}
            />
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
