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
import type { CourseResponse, CourseUpdate } from "../_schemas/course";

interface EditCourseDialogProps {
  course: CourseResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: CourseUpdate) => Promise<void> | void;
  isPending: boolean;
}

function buildForm(c: CourseResponse | null) {
  return {
    name: c?.name ?? "",
    code: c?.code ?? "",
    description: c?.description ?? "",
    duration_years: c ? String(c.duration_years) : "1",
  };
}

export function EditCourseDialog({
  course,
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: EditCourseDialogProps) {
  const [form, setForm] = useState(() => buildForm(course));
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setForm(buildForm(course));
      setError("");
    }
  }, [open, course]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim() || !form.code.trim()) {
      setError("Course name and code are required");
      return;
    }
    const duration = parseInt(form.duration_years, 10);
    if (!Number.isFinite(duration) || duration < 1 || duration > 10) {
      setError("Duration must be between 1 and 10 years");
      return;
    }

    try {
      await onSubmit({
        name: form.name.trim(),
        code: form.code.trim(),
        description: form.description.trim() || null,
        duration_years: duration,
      });
      onOpenChange(false);
    } catch (err: any) {
      setError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          "Failed to update course"
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>Edit Course</DialogTitle>
        <DialogDescription>
          Update course details. Changing duration affects how new batches span
          academic years.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit_course_name">Course Name *</Label>
              <Input
                id="edit_course_name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit_course_code">Course Code *</Label>
              <Input
                id="edit_course_code"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5 sm:max-w-[calc(50%-0.375rem)]">
            <Label htmlFor="edit_course_duration">Duration (years) *</Label>
            <Input
              id="edit_course_duration"
              type="number"
              min={1}
              max={10}
              value={form.duration_years}
              onChange={(e) =>
                setForm({ ...form, duration_years: e.target.value })
              }
              required
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit_course_description">Description</Label>
            <Input
              id="edit_course_description"
              value={form.description}
              onChange={(e) =>
                setForm({ ...form, description: e.target.value })
              }
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
              {isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
