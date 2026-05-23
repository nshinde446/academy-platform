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
  LectureNoShow,
  LectureResponse,
  NoShowReason,
} from "../_schemas/lecture";

interface MarkNoShowDialogProps {
  lecture: LectureResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: LectureNoShow) => Promise<void> | void;
  isPending: boolean;
}

const SELECT_CLASS =
  "flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

const REASONS: { value: NoShowReason; label: string }[] = [
  { value: "TEACHER_NO_SHOW", label: "Teacher didn't show up" },
  { value: "STUDENT_NO_SHOW", label: "Students didn't show up" },
  { value: "EXTERNAL", label: "External (weather, strike, power, etc.)" },
  { value: "OTHER", label: "Other (see notes)" },
];

export function MarkNoShowDialog({
  lecture,
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: MarkNoShowDialogProps) {
  const [reason, setReason] = useState<NoShowReason>("TEACHER_NO_SHOW");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setReason("TEACHER_NO_SHOW");
      setNotes("");
      setError("");
    }
  }, [open, lecture]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await onSubmit({
        no_show_reason: reason,
        notes: notes.trim() || null,
      });
      onOpenChange(false);
    } catch (err: any) {
      setError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          "Failed to mark no-show"
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup className="max-w-md">
        <DialogTitle>Mark as No-Show</DialogTitle>
        <DialogDescription>
          Different from cancel — captures that the scheduled lecture didn&apos;t
          happen due to teacher / student absence or external factors. Drives
          adherence reporting and surfaces syllabus gaps for makeups.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="noshow_reason">Reason *</Label>
            <select
              id="noshow_reason"
              value={reason}
              onChange={(e) => setReason(e.target.value as NoShowReason)}
              className={SELECT_CLASS}
              required
            >
              {REASONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="noshow_notes">Notes</Label>
            <Input
              id="noshow_notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional context"
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
            <Button type="submit" variant="destructive" disabled={isPending}>
              {isPending ? "Marking..." : "Mark no-show"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
