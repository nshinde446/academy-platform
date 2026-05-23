"use client";

import { useEffect, useMemo, useState } from "react";
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
  BatchSummary,
  ClassroomSummary,
  LectureResponse,
  LectureSessionCreate,
  TeacherSummary,
} from "../_schemas/lecture";

interface MergeLecturesDialogProps {
  batches: BatchSummary[];
  teachers: TeacherSummary[];
  classrooms: ClassroomSummary[];
  lectures: LectureResponse[];
  onSubmit: (data: LectureSessionCreate) => Promise<void> | void;
  isPending: boolean;
}

const SELECT_CLASS =
  "flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

function toDatetimeLocal(d: Date): string {
  const shifted = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
}

function isoLocalToIso(local: string): string {
  return new Date(local).toISOString();
}

function teacherName(t: TeacherSummary | undefined): string {
  if (!t) return "—";
  return [t.first_name, t.last_name].filter(Boolean).join(" ") || "—";
}

export function MergeLecturesDialog({
  batches,
  teachers,
  classrooms,
  lectures,
  onSubmit,
  isPending,
}: MergeLecturesDialogProps) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [teacherId, setTeacherId] = useState("");
  const [classroomId, setClassroomId] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  // Only scheduled lectures can be merged. Sort by scheduled_start asc.
  const mergeable = useMemo(
    () =>
      [...lectures]
        .filter((l) => l.lecture_status === "scheduled")
        .sort(
          (a, b) =>
            new Date(a.scheduled_start).getTime() -
            new Date(b.scheduled_start).getTime()
        ),
    [lectures]
  );

  const selectedLectures = useMemo(
    () => mergeable.filter((l) => selected.includes(l.id)),
    [mergeable, selected]
  );

  // Subject is locked to the first selected lecture — UI rejects mixed-subject merges.
  const subjectId = selectedLectures[0]?.subject_id ?? "";
  const mixedSubject = selectedLectures.some(
    (l) => l.subject_id !== subjectId
  );

  // Auto-fill teacher / classroom / window from the selection whenever it changes.
  useEffect(() => {
    if (selectedLectures.length === 0) {
      setTeacherId("");
      setClassroomId("");
      setStart("");
      setEnd("");
      return;
    }
    setTeacherId((cur) => cur || selectedLectures[0].teacher_id);
    setClassroomId(
      (cur) => cur || selectedLectures[0].classroom_id || ""
    );
    const minStart = selectedLectures.reduce(
      (m, l) =>
        new Date(l.scheduled_start) < new Date(m) ? l.scheduled_start : m,
      selectedLectures[0].scheduled_start
    );
    const maxEnd = selectedLectures.reduce(
      (m, l) => (new Date(l.scheduled_end) > new Date(m) ? l.scheduled_end : m),
      selectedLectures[0].scheduled_end
    );
    setStart((cur) => cur || toDatetimeLocal(new Date(minStart)));
    setEnd((cur) => cur || toDatetimeLocal(new Date(maxEnd)));
  }, [selectedLectures]);

  function reset() {
    setSelected([]);
    setTeacherId("");
    setClassroomId("");
    setStart("");
    setEnd("");
    setNotes("");
    setError("");
  }

  function toggle(id: string) {
    setSelected((s) =>
      s.includes(id) ? s.filter((x) => x !== id) : [...s, id]
    );
  }

  const batchIds = useMemo(
    () => Array.from(new Set(selectedLectures.map((l) => l.batch_id))),
    [selectedLectures]
  );

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (selectedLectures.length < 2) {
      return setError("Pick at least 2 scheduled lectures to merge");
    }
    if (mixedSubject) {
      return setError(
        "All merged lectures must teach the same subject — clear the odd one out"
      );
    }
    if (!teacherId) return setError("Pick the teacher who actually taught");
    if (!start) return setError("Actual start is required");
    if (end && new Date(end) <= new Date(start)) {
      return setError("End time must be after start time");
    }

    try {
      await onSubmit({
        teacher_id: teacherId,
        subject_id: subjectId,
        batch_ids: batchIds,
        lecture_ids: selectedLectures.map((l) => l.id),
        classroom_id: classroomId || null,
        topic_id: selectedLectures[0].topic_id,
        actual_start: isoLocalToIso(start),
        actual_end: end ? isoLocalToIso(end) : null,
        // If any plan was offline-with-a-classroom, default offline; otherwise online.
        delivery_mode: classroomId ? "offline" : "online",
        origin: "planned",
        notes: notes.trim() || null,
      });
      reset();
      setOpen(false);
    } catch (err: any) {
      setError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          "Failed to merge lectures"
      );
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
        render={
          <Button variant="outline" onClick={() => setOpen(true)}>
            Merge Lectures
          </Button>
        }
      />
      <DialogPopup className="max-w-2xl">
        <DialogTitle>Merge Lectures into One Session</DialogTitle>
        <DialogDescription>
          Combine two or more scheduled lectures (different batches) that were
          actually taught together. Creates one session linked to all selected
          plans. Original plans remain in place — cancel them separately if you
          don&apos;t want them counted as scheduled.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex flex-col gap-1.5">
            <Label>Scheduled lectures *</Label>
            {mergeable.length === 0 ? (
              <p className="text-sm text-muted-foreground italic">
                No scheduled lectures available to merge.
              </p>
            ) : (
              <div className="max-h-48 overflow-y-auto rounded-lg border divide-y">
                {mergeable.map((l) => {
                  const b = batches.find((x) => x.id === l.batch_id);
                  const t = teachers.find((x) => x.id === l.teacher_id);
                  return (
                    <label
                      key={l.id}
                      className="flex items-center gap-2 p-2 text-sm hover:bg-accent cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selected.includes(l.id)}
                        onChange={() => toggle(l.id)}
                      />
                      <span className="flex-1">
                        <span className="font-medium">
                          {b?.name ?? "?"}
                        </span>{" "}
                        · {teacherName(t)} ·{" "}
                        {new Date(l.scheduled_start).toLocaleString(undefined, {
                          month: "short",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
            {mixedSubject && (
              <p className="text-xs text-destructive">
                Selected lectures teach different subjects — merge requires one
                shared subject.
              </p>
            )}
            {selectedLectures.length >= 1 && !mixedSubject && (
              <p className="text-xs text-muted-foreground">
                {selectedLectures.length} selected ·{" "}
                {batchIds.length} batch{batchIds.length !== 1 ? "es" : ""}
              </p>
            )}
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="merge_teacher">Actual teacher *</Label>
              <select
                id="merge_teacher"
                value={teacherId}
                onChange={(e) => setTeacherId(e.target.value)}
                className={SELECT_CLASS}
                required
              >
                <option value="">Select a teacher...</option>
                {teachers.map((t) => (
                  <option key={t.id} value={t.id}>
                    {teacherName(t)}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="merge_classroom">Classroom</Label>
              <select
                id="merge_classroom"
                value={classroomId}
                onChange={(e) => setClassroomId(e.target.value)}
                className={SELECT_CLASS}
              >
                <option value="">No classroom (online)</option>
                {classrooms.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.code}) · cap {c.capacity}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="merge_start">Actual Start *</Label>
              <Input
                id="merge_start"
                type="datetime-local"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="merge_end">Actual End</Label>
              <Input
                id="merge_end"
                type="datetime-local"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="merge_notes">Notes</Label>
            <Input
              id="merge_notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional (e.g. teacher merged 2 batches into one room)"
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
            <Button
              type="submit"
              disabled={
                isPending || selectedLectures.length < 2 || mixedSubject
              }
            >
              {isPending ? "Merging..." : "Merge into session"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
