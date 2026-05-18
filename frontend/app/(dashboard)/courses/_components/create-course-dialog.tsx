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
import type { CourseCreate } from "../_schemas/course";

interface CreateCourseDialogProps {
  onSubmit: (data: Omit<CourseCreate, "branch_id">) => Promise<void> | void;
  isPending: boolean;
}

const EMPTY_FORM = {
  name: "",
  code: "",
  description: "",
  duration_years: "1",
};

export function CreateCourseDialog({
  onSubmit,
  isPending,
}: CreateCourseDialogProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState("");

  function reset() {
    setForm(EMPTY_FORM);
    setError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name || !form.code) {
      setError("Course name and code are required");
      return;
    }
    const duration = parseInt(form.duration_years, 10);
    if (!Number.isFinite(duration) || duration < 1) {
      setError("Duration must be at least 1 year");
      return;
    }

    try {
      await onSubmit({
        name: form.name,
        code: form.code,
        description: form.description || null,
        duration_years: duration,
      });
      reset();
      setOpen(false);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Failed to create course");
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
        render={<Button onClick={() => setOpen(true)}>Create Course</Button>}
      />
      <DialogPopup>
        <DialogTitle>Create Course</DialogTitle>
        <DialogDescription>
          Define a course. Multi-year programs (e.g., NEET 2-year) span batches
          across multiple academic years.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="course_name">Course Name *</Label>
              <Input
                id="course_name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="course_code">Course Code *</Label>
              <Input
                id="course_code"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="course_duration">Duration (years) *</Label>
              <Input
                id="course_duration"
                type="number"
                min={1}
                value={form.duration_years}
                onChange={(e) =>
                  setForm({ ...form, duration_years: e.target.value })
                }
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="course_description">Description</Label>
              <Input
                id="course_description"
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
                placeholder="Optional"
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
              {isPending ? "Creating..." : "Create"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
