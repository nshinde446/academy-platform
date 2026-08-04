"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import { useAcademicYears } from "@/app/(dashboard)/academic-years/_hooks/use-academic-years";
import type { CourseResponse } from "../_schemas/course";
import type { SubjectResponse } from "../_schemas/subject";
import {
  useCourseSubjects,
  useCreateSubject,
  useDeleteSubject,
  useSeedSubjects,
  useSyllabi,
} from "../_hooks/use-subjects";

const SELECT_CLASS =
  "flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

function apiErrorMessage(err: unknown): string | undefined {
  if (typeof err === "object" && err !== null) {
    const resp = (
      err as {
        response?: { data?: { error?: { message?: string }; detail?: string } };
      }
    ).response;
    return resp?.data?.error?.message ?? resp?.data?.detail;
  }
  return undefined;
}

interface ManageSubjectsDialogProps {
  course: CourseResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  branchId: string | undefined;
}

export function ManageSubjectsDialog({
  course,
  open,
  onOpenChange,
  branchId,
}: ManageSubjectsDialogProps) {
  const toast = useToast();
  const subjectsQuery = useCourseSubjects(branchId, course?.id);
  const syllabiQuery = useSyllabi();
  const yearsQuery = useAcademicYears(branchId);

  const seedMutation = useSeedSubjects(branchId);
  const createMutation = useCreateSubject(branchId);
  const deleteMutation = useDeleteSubject(branchId);

  const [syllabusKey, setSyllabusKey] = useState("");
  const [newName, setNewName] = useState("");
  const [newCode, setNewCode] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<SubjectResponse | null>(null);

  const subjects = subjectsQuery.data ?? [];
  const newestYear = useMemo(() => {
    const years = yearsQuery.data ?? [];
    if (years.length === 0) return undefined;
    return years.reduce((a, b) => (b.start_year > a.start_year ? b : a));
  }, [yearsQuery.data]);

  async function handleSeed() {
    if (!course || !branchId || !syllabusKey) return;
    try {
      const res = await seedMutation.mutateAsync({
        branch_id: branchId,
        course_id: course.id,
        syllabus_key: syllabusKey,
      });
      if (res.created > 0) {
        toast.success(
          "Subjects added",
          `${res.created} subject${res.created !== 1 ? "s" : ""} seeded for ${course.name}.`
        );
      } else {
        toast.info(
          "Already set up",
          "This course already has subjects, so none were added."
        );
      }
      setSyllabusKey("");
    } catch (err) {
      toast.error(
        "Could not seed subjects",
        apiErrorMessage(err) || "Please try again."
      );
    }
  }

  async function handleAdd() {
    if (!course || !branchId) return;
    const name = newName.trim();
    if (!name) return;
    if (!newestYear) {
      toast.error(
        "No academic year",
        "Create an academic year for this branch first."
      );
      return;
    }
    try {
      await createMutation.mutateAsync({
        course_id: course.id,
        academic_year_id: newestYear.id,
        name,
        code: newCode.trim() || name.slice(0, 3).toUpperCase(),
      });
      setNewName("");
      setNewCode("");
    } catch (err) {
      toast.error(
        "Could not add subject",
        apiErrorMessage(err) || "Please try again."
      );
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogPopup className="max-w-lg">
          <DialogTitle>Subjects — {course?.name ?? ""}</DialogTitle>
          <DialogDescription>
            Subjects for this course power the Schedule-Lecture dropdown. Seed the
            standard set from a syllabus, or add your own.
          </DialogDescription>

          <div className="mt-4 flex flex-col gap-5">
            {/* Current subjects */}
            <div className="flex flex-col gap-2">
              <Label>Current subjects</Label>
              {subjectsQuery.isLoading ? (
                <p className="text-sm text-muted-foreground">Loading…</p>
              ) : subjects.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No subjects yet — seed from a syllabus or add one below.
                </p>
              ) : (
                <ul className="flex flex-col divide-y rounded-lg border">
                  {subjects.map((s) => (
                    <li
                      key={s.id}
                      className="flex items-center justify-between gap-2 px-3 py-2"
                    >
                      <span className="flex items-center gap-2 text-sm">
                        <span className="font-medium">{s.name}</span>
                        <Badge variant="secondary">{s.code}</Badge>
                      </span>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setDeleteTarget(s)}
                        aria-label={`Remove subject ${s.name}`}
                      >
                        Remove
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Seed from syllabus */}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="seed_syllabus">Seed from syllabus</Label>
              <div className="flex gap-2">
                <select
                  id="seed_syllabus"
                  value={syllabusKey}
                  onChange={(e) => setSyllabusKey(e.target.value)}
                  className={SELECT_CLASS}
                >
                  <option value="">Select a syllabus…</option>
                  {(syllabiQuery.data ?? []).map((o) => (
                    <option key={o.key} value={o.key}>
                      {o.label}
                    </option>
                  ))}
                </select>
                <Button
                  type="button"
                  onClick={handleSeed}
                  disabled={!syllabusKey || seedMutation.isPending}
                >
                  {seedMutation.isPending ? "Seeding…" : "Seed"}
                </Button>
              </div>
            </div>

            {/* Add one subject */}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="new_subject_name">Add a subject</Label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  id="new_subject_name"
                  placeholder="Subject name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="sm:flex-1"
                />
                <Input
                  aria-label="Subject code (optional)"
                  placeholder="Code (optional)"
                  value={newCode}
                  onChange={(e) => setNewCode(e.target.value)}
                  className="sm:w-32"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleAdd}
                  disabled={!newName.trim() || createMutation.isPending}
                >
                  {createMutation.isPending ? "Adding…" : "Add"}
                </Button>
              </div>
            </div>
          </div>

          <div className="mt-6 flex justify-end">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  Done
                </Button>
              }
            />
          </div>
        </DialogPopup>
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title="Remove subject?"
        description={
          deleteTarget
            ? `Remove "${deleteTarget.name}" from this course? Subjects used by scheduled lectures cannot be removed.`
            : ""
        }
        confirmLabel="Remove"
        destructive
        onConfirm={async () => {
          if (!deleteTarget) return;
          await deleteMutation.mutateAsync(deleteTarget.id);
          setDeleteTarget(null);
        }}
      />
    </>
  );
}
