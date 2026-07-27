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
  LectureReschedule,
  LectureResponse,
} from "../_schemas/lecture";

interface ClassroomOption {
  id: string;
  name: string;
}

interface RescheduleDialogProps {
  lecture: LectureResponse | null;
  classrooms: ClassroomOption[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: LectureReschedule) => Promise<void> | void;
  isPending: boolean;
}

const SELECT_CLASS =
  "flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

// ISO → value a <input type="datetime-local"> expects (local wall-clock).
function toDatetimeLocal(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const shifted = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
}

function localToIso(local: string): string | null {
  if (!local) return null;
  const d = new Date(local);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export function RescheduleDialog({
  lecture,
  classrooms,
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: RescheduleDialogProps) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [classroomId, setClassroomId] = useState("");
  const [error, setError] = useState("");

  // Prefill from the lecture's current schedule each time it opens.
  useEffect(() => {
    if (open && lecture) {
      setStart(toDatetimeLocal(lecture.scheduled_start));
      setEnd(toDatetimeLocal(lecture.scheduled_end));
      setClassroomId(lecture.classroom_id ?? "");
      setError("");
    }
  }, [open, lecture]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const startIso = localToIso(start);
    const endIso = localToIso(end);
    if (!startIso || !endIso) {
      setError("Pick a new start and end time.");
      return;
    }
    if (new Date(endIso).getTime() <= new Date(startIso).getTime()) {
      setError("End time must be after the start time.");
      return;
    }
    try {
      await onSubmit({
        scheduled_start: startIso,
        scheduled_end: endIso,
        classroom_id: classroomId || null,
      });
      onOpenChange(false);
    } catch (err: unknown) {
      const e2 = err as {
        response?: { data?: { error?: { message?: string }; detail?: string } };
      };
      setError(
        e2?.response?.data?.error?.message ||
          e2?.response?.data?.detail ||
          "Failed to reschedule"
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup className="max-w-md">
        <DialogTitle>Reschedule lecture</DialogTitle>
        <DialogDescription>
          Move this lecture to a new time (and optionally a new room). The
          backend re-checks teacher, batch, and classroom conflicts. Only
          scheduled lectures can be rescheduled.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="reschedule_start">New start *</Label>
              <Input
                id="reschedule_start"
                type="datetime-local"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="reschedule_end">New end *</Label>
              <Input
                id="reschedule_end"
                type="datetime-local"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reschedule_room">Room</Label>
            <select
              id="reschedule_room"
              value={classroomId}
              onChange={(e) => setClassroomId(e.target.value)}
              className={SELECT_CLASS}
            >
              <option value="">Keep / unassigned</option>
              {classrooms.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
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
              {isPending ? "Rescheduling..." : "Reschedule"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
