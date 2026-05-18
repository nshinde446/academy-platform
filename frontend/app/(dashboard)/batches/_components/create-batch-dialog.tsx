"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
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
  const [selectedStartYear, setSelectedStartYear] = useState("");
  const [error, setError] = useState("");
  const queryClient = useQueryClient();

  useEffect(() => {
    if (open) {
      queryClient.invalidateQueries({ queryKey: ["academic-years"] });
      queryClient.invalidateQueries({ queryKey: ["courses"] });
    }
  }, [open, queryClient]);

  const sortedYears = useMemo(
    () => [...academicYears].sort((a, b) => a.start_year - b.start_year),
    [academicYears]
  );

  const courseId = selectedCourse || courses[0]?.id || "";
  const startYearId = selectedStartYear || sortedYears[0]?.id || "";
  const course = courses.find((c) => c.id === courseId);
  const startYear = sortedYears.find((y) => y.id === startYearId);
  const duration = course?.duration_years ?? 1;
  const endYearTarget = startYear ? startYear.start_year + duration - 1 : null;
  const endYear =
    endYearTarget !== null
      ? sortedYears.find((y) => y.start_year === endYearTarget)
      : undefined;

  function reset() {
    setForm(EMPTY_FORM);
    setSelectedCourse("");
    setSelectedStartYear("");
    setError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name || !form.code) {
      setError("Batch name and code are required");
      return;
    }
    if (!courseId) {
      setError("No course available. Create a course first.");
      return;
    }
    if (!startYearId) {
      setError("No academic year available. Create one first.");
      return;
    }
    if (!endYear) {
      setError(
        `Cannot find academic year for end year ${endYearTarget}. Create it first.`
      );
      return;
    }

    try {
      await onSubmit({
        start_academic_year_id: startYearId,
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
        <DialogDescription>
          A batch instantiates a course for a student group. Multi-year courses
          (e.g., NEET 2-year) span across two academic years automatically.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          {courses.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="batch_course">Course</Label>
              <select
                id="batch_course"
                value={courseId}
                onChange={(e) => setSelectedCourse(e.target.value)}
                className="flex h-8 w-full rounded-lg border border-input bg-background px-3 text-sm"
              >
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.code}) — {c.duration_years}{" "}
                    {c.duration_years === 1 ? "yr" : "yrs"}
                  </option>
                ))}
              </select>
            </div>
          )}

          {sortedYears.length > 0 && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="batch_start_year">Start Academic Year</Label>
                <select
                  id="batch_start_year"
                  value={startYearId}
                  onChange={(e) => setSelectedStartYear(e.target.value)}
                  className="flex h-8 w-full rounded-lg border border-input bg-background px-3 text-sm"
                >
                  {sortedYears.map((y) => (
                    <option key={y.id} value={y.id}>
                      {y.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="batch_end_year">End Academic Year</Label>
                <Input
                  id="batch_end_year"
                  value={
                    endYear
                      ? endYear.name
                      : endYearTarget !== null
                      ? `Missing (${endYearTarget})`
                      : "—"
                  }
                  readOnly
                  className="bg-muted"
                />
              </div>
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
