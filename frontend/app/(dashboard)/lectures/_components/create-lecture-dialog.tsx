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
  useTopicsBySubject,
} from "../_hooks/use-lectures";
import type {
  BatchSummary,
  LectureCreate,
  TeacherSummary,
} from "../_schemas/lecture";

interface CreateLectureDialogProps {
  branchId: string | undefined;
  batches: BatchSummary[];
  teachers: TeacherSummary[];
  onSubmit: (data: LectureCreate) => Promise<void> | void;
  isPending: boolean;
}

const SELECT_CLASS =
  "flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

function isoLocalToIso(local: string): string {
  // datetime-local lacks timezone — assume the user's local zone.
  const d = new Date(local);
  return d.toISOString();
}

function defaultStart(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset() + 60);
  d.setSeconds(0, 0);
  return d.toISOString().slice(0, 16);
}

function defaultEnd(start: string): string {
  const d = new Date(start);
  if (Number.isNaN(d.getTime())) return start;
  d.setHours(d.getHours() + 1);
  return d.toISOString().slice(0, 16);
}

export function CreateLectureDialog({
  branchId,
  batches,
  teachers,
  onSubmit,
  isPending,
}: CreateLectureDialogProps) {
  const [open, setOpen] = useState(false);
  const [batchId, setBatchId] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [topicId, setTopicId] = useState("");
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

  const subjects = subjectsQuery.data ?? [];
  const topics = topicsQuery.data ?? [];

  // When batch changes, clear stale subject/topic.
  useEffect(() => {
    setSubjectId("");
    setTopicId("");
  }, [batchId]);

  // When subject changes, clear stale topic.
  useEffect(() => {
    setTopicId("");
  }, [subjectId]);

  function reset() {
    setBatchId("");
    setTeacherId("");
    setSubjectId("");
    setTopicId("");
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

    try {
      await onSubmit({
        batch_id: batchId,
        teacher_id: teacherId,
        subject_id: subjectId,
        topic_id: topicId || null,
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
          <Button onClick={() => setOpen(true)}>Schedule Lecture</Button>
        }
      />
      <DialogPopup className="max-w-2xl">
        <DialogTitle>Schedule Lecture</DialogTitle>
        <DialogDescription>
          Pick a batch and the subject + topic dropdowns will filter to its
          course. Backend rejects scheduling conflicts on teacher, batch, or
          classroom.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

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
              <Label htmlFor="lecture_teacher">Teacher *</Label>
              <select
                id="lecture_teacher"
                value={teacherId}
                onChange={(e) => setTeacherId(e.target.value)}
                className={SELECT_CLASS}
                required
              >
                <option value="">Select a teacher...</option>
                {teachers.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.first_name} {t.last_name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
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

          {deliveryMode === "offline" && (
            <p className="text-xs text-muted-foreground">
              Offline lectures require a classroom — backend rejects the create
              call until classroom assignment is wired up.
            </p>
          )}

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
