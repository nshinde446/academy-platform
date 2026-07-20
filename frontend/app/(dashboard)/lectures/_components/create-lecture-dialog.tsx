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
import {
  useSubjectsByCourse,
  useTeachersBySubject,
  useTopicsBySubject,
} from "../_hooks/use-lectures";
import type {
  BatchSummary,
  ClassroomSummary,
  LectureCreate,
} from "../_schemas/lecture";

interface CreateLectureDialogProps {
  branchId: string | undefined;
  batches: BatchSummary[];
  classrooms: ClassroomSummary[];
  onSubmit: (data: LectureCreate) => Promise<void> | void;
  isPending: boolean;
  /** Hide the built-in trigger when the dialog is driven from elsewhere. */
  hideTrigger?: boolean;
  /** Controlled open state. Omit to let the dialog own it. */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /**
   * Pre-fill the time window — used when a calendar slot is clicked. Applied
   * each time the dialog opens with a new window.
   */
  prefillStart?: Date | null;
  prefillEnd?: Date | null;
}

const SELECT_CLASS =
  "flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

function isoLocalToIso(local: string): string {
  // datetime-local lacks timezone — assume the user's local zone.
  const d = new Date(local);
  return d.toISOString();
}

function toDatetimeLocal(d: Date): string {
  // Shift by the local timezone offset so toISOString prints local wall-clock.
  const shifted = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
}

function defaultStart(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() + 60);
  d.setSeconds(0, 0);
  return toDatetimeLocal(d);
}

function defaultEnd(start: string): string {
  const d = new Date(start);
  if (Number.isNaN(d.getTime())) return start;
  d.setHours(d.getHours() + 1);
  return toDatetimeLocal(d);
}

export function CreateLectureDialog({
  branchId,
  batches,
  classrooms,
  onSubmit,
  isPending,
  hideTrigger,
  open: openProp,
  onOpenChange,
  prefillStart,
  prefillEnd,
}: CreateLectureDialogProps) {
  const [openState, setOpenState] = useState(false);
  const open = openProp ?? openState;
  const setOpen = (next: boolean) => {
    setOpenState(next);
    onOpenChange?.(next);
  };
  const [batchId, setBatchId] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [topicId, setTopicId] = useState("");
  const [classroomId, setClassroomId] = useState("");
  const [start, setStart] = useState(defaultStart());
  const [end, setEnd] = useState(defaultEnd(defaultStart()));
  const [deliveryMode, setDeliveryMode] = useState("online");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  const selectedBatch = useMemo(
    () => batches.find((b) => b.id === batchId),
    [batches, batchId]
  );

  const subjectsQuery = useSubjectsByCourse(branchId, selectedBatch?.course_id);
  const topicsQuery = useTopicsBySubject(branchId, subjectId || undefined);
  // Subject→Teacher lock: only teachers assigned to the picked subject are
  // offered. The backend still validates on save — this is just the UX half.
  const teachersQuery = useTeachersBySubject(branchId, subjectId || undefined);

  const subjects = subjectsQuery.data ?? [];
  const topics = topicsQuery.data ?? [];
  const teachers = teachersQuery.data ?? [];

  // When batch changes, clear stale subject/topic/teacher.
  useEffect(() => {
    setSubjectId("");
    setTopicId("");
    setTeacherId("");
  }, [batchId]);

  // When subject changes, clear stale topic + teacher (teacher list is
  // subject-scoped, so the previously picked teacher may no longer qualify).
  useEffect(() => {
    setTopicId("");
    setTeacherId("");
  }, [subjectId]);

  // Apply a calendar-slot pre-fill. Derived during render rather than in an
  // effect so the first paint already shows the clicked window.
  const prefillKey = prefillStart
    ? `${prefillStart.getTime()}-${prefillEnd?.getTime() ?? ""}`
    : "";
  const [appliedPrefill, setAppliedPrefill] = useState("");
  if (open && prefillKey && prefillKey !== appliedPrefill) {
    setAppliedPrefill(prefillKey);
    setStart(toDatetimeLocal(prefillStart!));
    setEnd(
      prefillEnd
        ? toDatetimeLocal(prefillEnd)
        : defaultEnd(toDatetimeLocal(prefillStart!)),
    );
  }

  function reset() {
    setAppliedPrefill("");
    setBatchId("");
    setTeacherId("");
    setSubjectId("");
    setTopicId("");
    setClassroomId("");
    const s = defaultStart();
    setStart(s);
    setEnd(defaultEnd(s));
    setDeliveryMode("online");
    setNotes("");
    setError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!batchId) {
      setError("Pick a batch");
      return;
    }
    if (!teacherId) {
      setError("Pick a teacher");
      return;
    }
    if (!subjectId) {
      setError("Pick a subject");
      return;
    }
    if (!start || !end) {
      setError("Both start and end are required");
      return;
    }
    if (new Date(end) <= new Date(start)) {
      setError("End time must be after start time");
      return;
    }
    if (deliveryMode === "offline" && !classroomId) {
      setError("Offline lectures require a classroom");
      return;
    }

    try {
      await onSubmit({
        batch_id: batchId,
        teacher_id: teacherId,
        subject_id: subjectId,
        topic_id: topicId || null,
        classroom_id: classroomId || null,
        scheduled_start: isoLocalToIso(start),
        scheduled_end: isoLocalToIso(end),
        delivery_mode: deliveryMode,
        notes: notes.trim() || null,
      });
      reset();
      setOpen(false);
    } catch (err: any) {
      setError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          "Failed to schedule lecture"
      );
    }
  }

  const subjectsDisabled = !selectedBatch || subjectsQuery.isLoading;
  const topicsDisabled = !subjectId || topicsQuery.isLoading;
  const teachersDisabled = !subjectId || teachersQuery.isLoading;

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        setOpen(isOpen);
        if (!isOpen) reset();
      }}
    >
      {!hideTrigger && (
        <DialogTrigger
          render={
            <Button onClick={() => setOpen(true)}>Schedule Lecture</Button>
          }
        />
      )}
      <DialogPopup className="max-w-2xl">
        <DialogTitle>Schedule Lecture</DialogTitle>
        <DialogDescription>
          Batch → Subject → Teacher cascade: each dropdown filters the next, so
          only teachers assigned to the chosen subject are offered. Backend
          enforces the same lock and rejects teacher / batch / classroom
          scheduling conflicts.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          {/* Cascade: Batch → Subject (course-scoped) → Teacher (subject-scoped). */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lecture_batch">Batch *</Label>
              <select
                id="lecture_batch"
                value={batchId}
                onChange={(e) => setBatchId(e.target.value)}
                className={SELECT_CLASS}
                required
              >
                <option value="">Select a batch...</option>
                {batches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name} ({b.code})
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lecture_subject">Subject *</Label>
              <select
                id="lecture_subject"
                value={subjectId}
                onChange={(e) => setSubjectId(e.target.value)}
                className={SELECT_CLASS}
                disabled={subjectsDisabled}
                required
              >
                <option value="">
                  {!selectedBatch
                    ? "Pick a batch first"
                    : subjectsQuery.isLoading
                    ? "Loading..."
                    : subjects.length === 0
                    ? "No subjects for this course"
                    : "Select a subject..."}
                </option>
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.code})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lecture_teacher">Teacher *</Label>
              <select
                id="lecture_teacher"
                value={teacherId}
                onChange={(e) => setTeacherId(e.target.value)}
                className={SELECT_CLASS}
                disabled={teachersDisabled}
                required
              >
                <option value="">
                  {!subjectId
                    ? "Pick a subject first"
                    : teachersQuery.isLoading
                    ? "Loading..."
                    : teachers.length === 0
                    ? "No teacher assigned to this subject"
                    : "Select a teacher..."}
                </option>
                {teachers.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.first_name} {t.last_name}
                  </option>
                ))}
              </select>
              {subjectId && !teachersQuery.isLoading && teachers.length === 0 && (
                <p className="text-xs text-destructive">
                  Assign this subject to a teacher (on Teachers) before
                  scheduling it.
                </p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lecture_topic">Topic</Label>
              <select
                id="lecture_topic"
                value={topicId}
                onChange={(e) => setTopicId(e.target.value)}
                className={SELECT_CLASS}
                disabled={topicsDisabled}
              >
                <option value="">
                  {!subjectId
                    ? "Pick a subject first"
                    : topicsQuery.isLoading
                    ? "Loading..."
                    : topics.length === 0
                    ? "No topics — leave blank"
                    : "Select a topic (optional)..."}
                </option>
                {topics.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lecture_start">Scheduled Start *</Label>
              <Input
                id="lecture_start"
                type="datetime-local"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lecture_end">Scheduled End *</Label>
              <Input
                id="lecture_end"
                type="datetime-local"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lecture_mode">Delivery Mode</Label>
              <select
                id="lecture_mode"
                value={deliveryMode}
                onChange={(e) => setDeliveryMode(e.target.value)}
                className={SELECT_CLASS}
              >
                <option value="online">Online</option>
                <option value="offline">Offline</option>
                <option value="hybrid">Hybrid</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lecture_notes">Notes</Label>
              <Input
                id="lecture_notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional"
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lecture_classroom">
              Classroom{deliveryMode === "offline" ? " *" : ""}
            </Label>
            <select
              id="lecture_classroom"
              value={classroomId}
              onChange={(e) => setClassroomId(e.target.value)}
              className={SELECT_CLASS}
              required={deliveryMode === "offline"}
            >
              <option value="">
                {classrooms.length === 0
                  ? "No classrooms yet — create one first"
                  : deliveryMode === "offline"
                  ? "Select a classroom..."
                  : "Select a classroom (optional)..."}
              </option>
              {classrooms.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.code}) · cap {c.capacity}
                </option>
              ))}
            </select>
            {deliveryMode === "offline" && classrooms.length === 0 && (
              <p className="text-xs text-destructive">
                You need at least one classroom in this branch before scheduling
                an offline lecture.
              </p>
            )}
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
              {isPending ? "Scheduling..." : "Schedule"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
