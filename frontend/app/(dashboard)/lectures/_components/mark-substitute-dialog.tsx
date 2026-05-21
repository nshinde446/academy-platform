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
  ChangeReason,
  LectureResponse,
  LectureSubstitute,
  TeacherSummary,
} from "../_schemas/lecture";

interface MarkSubstituteDialogProps {
  lecture: LectureResponse | null;
  teachers: TeacherSummary[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: LectureSubstitute) => Promise<void> | void;
  isPending: boolean;
}

const SELECT_CLASS =
  "flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

const REASONS: { value: ChangeReason; label: string }[] = [
  { value: "SUBSTITUTE", label: "Substitute (scheduled teacher absent)" },
  { value: "SUBJECT_SWAP", label: "Subject swap (different subject taught)" },
  { value: "TOPIC_CHANGE", label: "Topic change (different topic taught)" },
  { value: "COMBINED_BATCH", label: "Combined batch (merged with another)" },
  { value: "OTHER", label: "Other (see notes)" },
];

function teacherName(t: TeacherSummary | undefined): string {
  if (!t) return "—";
  return [t.first_name, t.last_name].filter(Boolean).join(" ") || "—";
}

export function MarkSubstituteDialog({
  lecture,
  teachers,
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: MarkSubstituteDialogProps) {
  const [actualTeacherId, setActualTeacherId] = useState("");
  const [reason, setReason] = useState<ChangeReason>("SUBSTITUTE");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setActualTeacherId(lecture?.actual_teacher_id ?? "");
      setReason((lecture?.change_reason as ChangeReason) ?? "SUBSTITUTE");
      setNotes(lecture?.change_notes ?? "");
      setError("");
    }
  }, [open, lecture]);

  const scheduledTeacher = teachers.find(
    (t) => t.id === lecture?.teacher_id
  );

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!actualTeacherId) {
      setError("Pick the teacher who actually took the lecture");
      return;
    }
    if (actualTeacherId === lecture?.teacher_id) {
      setError("Substitute must differ from the scheduled teacher");
      return;
    }
    try {
      await onSubmit({
        actual_teacher_id: actualTeacherId,
        change_reason: reason,
        change_notes: notes.trim() || null,
      });
      onOpenChange(false);
    } catch (err: any) {
      setError(
        err.response?.data?.error?.message ||
          err.response?.data?.detail ||
          "Failed to record substitute"
      );
    }
  }

  async function handleClear() {
    setError("");
    try {
      await onSubmit({
        actual_teacher_id: null,
        change_reason: null,
        change_notes: null,
      });
      onOpenChange(false);
    } catch (err: any) {
      setError(
        err.response?.data?.error?.message || "Failed to clear substitute"
      );
    }
  }

  const hasExisting = !!lecture?.actual_teacher_id;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup className="max-w-lg">
        <DialogTitle>
          {hasExisting ? "Edit Substitute" : "Mark Substitute Teacher"}
        </DialogTitle>
        <DialogDescription>
          Record who actually delivered this lecture when it differs from the
          schedule. The original schedule is preserved for the audit trail.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="rounded-lg border bg-muted/40 p-3 text-sm">
            <p>
              <span className="text-muted-foreground">Scheduled teacher:</span>{" "}
              <span className="font-medium">
                {teacherName(scheduledTeacher)}
              </span>
            </p>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sub_teacher">Actual teacher *</Label>
            <select
              id="sub_teacher"
              value={actualTeacherId}
              onChange={(e) => setActualTeacherId(e.target.value)}
              className={SELECT_CLASS}
              required
            >
              <option value="">Select the substitute...</option>
              {teachers
                .filter((t) => t.id !== lecture?.teacher_id)
                .map((t) => (
                  <option key={t.id} value={t.id}>
                    {teacherName(t)}
                  </option>
                ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sub_reason">Reason</Label>
            <select
              id="sub_reason"
              value={reason}
              onChange={(e) => setReason(e.target.value as ChangeReason)}
              className={SELECT_CLASS}
            >
              {REASONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sub_notes">Notes</Label>
            <Input
              id="sub_notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional context (e.g. teacher sick, requested swap)"
            />
          </div>

          <div className="flex flex-wrap justify-end gap-2 pt-2">
            {hasExisting && (
              <Button
                type="button"
                variant="outline"
                onClick={handleClear}
                disabled={isPending}
              >
                Clear substitute
              </Button>
            )}
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
