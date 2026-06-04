"use client";

import { useEffect, useMemo, useState } from "react";
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
import {
  useSubjectsByCourse,
  useTopicsBySubject,
} from "../_hooks/use-lectures";
import type {
  BatchSummary,
  ClassroomSummary,
  LectureResponse,
  LectureSessionCreate,
  TeacherSummary,
} from "../_schemas/lecture";

interface RecordMakeupDialogProps {
  branchId: string | undefined;
  batches: BatchSummary[];
  teachers: TeacherSummary[];
  classrooms: ClassroomSummary[];
  lectures: LectureResponse[];
  onSubmit: (data: LectureSessionCreate) => Promise<void> | void;
  isPending: boolean;
  /** Controlled-open. Parent owns the trigger button. */
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Pre-link to a missed lecture when the dialog opens. */
  prefillLectureId?: string | null;
}

const SELECT_CLASS =
  "flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

function isoLocalToIso(local: string): string {
  return new Date(local).toISOString();
}

function toDatetimeLocal(d: Date): string {
  const shifted = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
}

function defaultStart(): string {
  const d = new Date();
  d.setMinutes(0, 0, 0);
  return toDatetimeLocal(d);
}

function defaultEnd(start: string): string {
  const d = new Date(start);
  if (Number.isNaN(d.getTime())) return start;
  d.setHours(d.getHours() + 1);
  return toDatetimeLocal(d);
}

export function RecordMakeupDialog({
  branchId,
  batches,
  teachers,
  classrooms,
  lectures,
  onSubmit,
  isPending,
  open,
  onOpenChange,
  prefillLectureId,
}: RecordMakeupDialogProps) {
  const [linkedLectureId, setLinkedLectureId] = useState("");
  const [batchId, setBatchId] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [topicId, setTopicId] = useState("");
  const [classroomId, setClassroomId] = useState("");
  const [start, setStart] = useState(defaultStart());
  const [end, setEnd] = useState(defaultEnd(defaultStart()));
  const [deliveryMode, setDeliveryMode] = useState("offline");
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

  const missedLectures = useMemo(
    () =>
      lectures.filter(
        (l) =>
          l.lecture_status === "cancelled" ||
          (l.lecture_status === "scheduled" &&
            new Date(l.scheduled_end) < new Date())
      ),
    [lectures]
  );

  function reset() {
    setLinkedLectureId("");
    setBatchId("");
    setTeacherId("");
    setSubjectId("");
    setTopicId("");
    setClassroomId("");
    const s = defaultStart();
    setStart(s);
    setEnd(defaultEnd(s));
    setDeliveryMode("offline");
    setNotes("");
    setError("");
  }

  // Prefill from linked missed lecture.
  useEffect(() => {
    if (!linkedLectureId) return;
    const l = lectures.find((x) => x.id === linkedLectureId);
    if (!l) return;
    setBatchId(l.batch_id);
    setSubjectId(l.subject_id);
    setTeacherId(l.teacher_id);
    if (l.topic_id) setTopicId(l.topic_id);
    if (l.classroom_id) setClassroomId(l.classroom_id);
    setDeliveryMode(l.delivery_mode);
  }, [linkedLectureId, lectures]);

  // When the parent passes a prefillLectureId alongside open=true, pre-select
  // the linked lecture so the MSA Quick Action lands the user on the right
  // makeup row without typing.
  useEffect(() => {
    if (open && prefillLectureId) {
      setLinkedLectureId(prefillLectureId);
    }
  }, [open, prefillLectureId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!batchId) return setError("Pick a batch");
    if (!teacherId) return setError("Pick a teacher");
    if (!subjectId) return setError("Pick a subject");
    if (!start) return setError("Start time is required");
    if (end && new Date(end) <= new Date(start)) {
      return setError("End time must be after start time");
    }
    if (deliveryMode === "offline" && !classroomId) {
      return setError("Offline sessions require a classroom");
    }

    try {
      await onSubmit({
        teacher_id: teacherId,
        subject_id: subjectId,
        batch_ids: [batchId],
        lecture_ids: linkedLectureId ? [linkedLectureId] : [],
        classroom_id: classroomId || null,
        topic_id: topicId || null,
        actual_start: isoLocalToIso(start),
        actual_end: end ? isoLocalToIso(end) : null,
        delivery_mode: deliveryMode,
        origin: linkedLectureId ? "makeup" : "ad_hoc",
        notes: notes.trim() || null,
      });
      reset();
      onOpenChange(false);
    } catch (err: any) {
      setError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          "Failed to record session"
      );
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        onOpenChange(isOpen);
        if (!isOpen) reset();
      }}
    >
      <DialogPopup className="max-w-2xl">
        <DialogTitle>Record Makeup / Ad-hoc Lecture</DialogTitle>
        <DialogDescription>
          Use this when a class actually happened without a matching schedule,
          or to record a makeup for a cancelled lecture. Optionally link the
          missed plan so attendance ties back to it.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="makeup_linked">
              Linked missed lecture (optional)
            </Label>
            <select
              id="makeup_linked"
              value={linkedLectureId}
              onChange={(e) => setLinkedLectureId(e.target.value)}
              className={SELECT_CLASS}
            >
              <option value="">No link — pure ad-hoc</option>
              {missedLectures.map((l) => {
                const b = batches.find((x) => x.id === l.batch_id);
                return (
                  <option key={l.id} value={l.id}>
                    {b?.name ?? "?"} · {l.lecture_status} ·{" "}
                    {new Date(l.scheduled_start).toLocaleDateString()}
                  </option>
                );
              })}
            </select>
            <p className="text-xs text-muted-foreground">
              Linking sets origin=makeup; leaving blank sets origin=ad_hoc.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="makeup_batch">Batch *</Label>
              <select
                id="makeup_batch"
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
              <Label htmlFor="makeup_teacher">Teacher *</Label>
              <select
                id="makeup_teacher"
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
              <Label htmlFor="makeup_subject">Subject *</Label>
              <select
                id="makeup_subject"
                value={subjectId}
                onChange={(e) => setSubjectId(e.target.value)}
                className={SELECT_CLASS}
                disabled={!selectedBatch || subjectsQuery.isLoading}
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
              <Label htmlFor="makeup_topic">Topic</Label>
              <select
                id="makeup_topic"
                value={topicId}
                onChange={(e) => setTopicId(e.target.value)}
                className={SELECT_CLASS}
                disabled={!subjectId || topicsQuery.isLoading}
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
              <Label htmlFor="makeup_start">Actual Start *</Label>
              <Input
                id="makeup_start"
                type="datetime-local"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="makeup_end">Actual End</Label>
              <Input
                id="makeup_end"
                type="datetime-local"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="makeup_mode">Delivery Mode</Label>
              <select
                id="makeup_mode"
                value={deliveryMode}
                onChange={(e) => setDeliveryMode(e.target.value)}
                className={SELECT_CLASS}
              >
                <option value="offline">Offline</option>
                <option value="online">Online</option>
                <option value="hybrid">Hybrid</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="makeup_classroom">
                Classroom{deliveryMode === "offline" ? " *" : ""}
              </Label>
              <select
                id="makeup_classroom"
                value={classroomId}
                onChange={(e) => setClassroomId(e.target.value)}
                className={SELECT_CLASS}
                required={deliveryMode === "offline"}
              >
                <option value="">
                  {classrooms.length === 0
                    ? "No classrooms yet"
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
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="makeup_notes">Notes</Label>
            <Input
              id="makeup_notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional (e.g. weekend makeup for Tuesday's cancelled class)"
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
              {isPending ? "Recording..." : "Record session"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
