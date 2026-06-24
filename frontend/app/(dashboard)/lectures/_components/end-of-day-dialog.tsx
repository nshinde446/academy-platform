"use client";

import { useEffect, useMemo, useState } from "react";
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
import { useTopicsBySubject } from "../_hooks/use-lectures";
import type { LectureActuals, LectureResponse } from "../_schemas/lecture";

interface EndOfDayDialogProps {
  branchId: string | undefined;
  lecture: LectureResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (lectureId: string, data: LectureActuals) => Promise<void> | void;
  isPending: boolean;
}

const SELECT_CLASS =
  "flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

// Lecture is "late" past this many minutes after the scheduled start — mirror
// of the backend LATE_THRESHOLD_MIN so the preview matches what gets stored.
const LATE_THRESHOLD_MIN = 10;

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

export function EndOfDayDialog({
  branchId,
  lecture,
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: EndOfDayDialogProps) {
  const [actualStart, setActualStart] = useState("");
  const [actualEnd, setActualEnd] = useState("");
  const [topicId, setTopicId] = useState("");
  const [error, setError] = useState("");

  const topicsQuery = useTopicsBySubject(branchId, lecture?.subject_id);
  const topics = topicsQuery.data ?? [];

  // Seed the form from the lecture: prefer any actuals already recorded, else
  // default to the scheduled times so the admin only nudges the minutes.
  useEffect(() => {
    if (open && lecture) {
      setActualStart(
        toDatetimeLocal(lecture.actual_start ?? lecture.scheduled_start)
      );
      setActualEnd(toDatetimeLocal(lecture.actual_end ?? lecture.scheduled_end));
      setTopicId(lecture.topic_id ?? "");
      setError("");
    }
  }, [open, lecture]);

  // Live punctuality + duration preview — no round-trip needed.
  const preview = useMemo(() => {
    if (!lecture || !actualStart) return null;
    const sched = new Date(lecture.scheduled_start).getTime();
    const start = new Date(actualStart).getTime();
    if (Number.isNaN(start) || Number.isNaN(sched)) return null;
    const lateBy = Math.round((start - sched) / 60_000);
    const isLate = lateBy > LATE_THRESHOLD_MIN;
    let durationMin: number | null = null;
    if (actualEnd) {
      const end = new Date(actualEnd).getTime();
      if (!Number.isNaN(end) && end > start) {
        durationMin = Math.round((end - start) / 60_000);
      }
    }
    return { isLate, lateBy, durationMin };
  }, [lecture, actualStart, actualEnd]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!lecture) return;
    const startIso = localToIso(actualStart);
    if (!startIso) {
      setError("Actual start time is required");
      return;
    }
    const endIso = localToIso(actualEnd);
    if (endIso && new Date(endIso) <= new Date(startIso)) {
      setError("Actual end must be after actual start");
      return;
    }
    try {
      await onSubmit(lecture.id, {
        actual_start: startIso,
        actual_end: endIso,
        topic_id: topicId || null,
      });
      onOpenChange(false);
    } catch (err: any) {
      setError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          "Failed to save actuals"
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup className="max-w-lg">
        <DialogTitle>End-of-Day Update</DialogTitle>
        <DialogDescription>
          Record what actually happened — start, end, and topic taught. Setting
          an end time completes the lecture; the late-start flag and teaching
          duration are computed for you.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="eod_start">Actual Start *</Label>
              <Input
                id="eod_start"
                type="datetime-local"
                value={actualStart}
                onChange={(e) => setActualStart(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="eod_end">Actual End</Label>
              <Input
                id="eod_end"
                type="datetime-local"
                value={actualEnd}
                onChange={(e) => setActualEnd(e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="eod_topic">Topic Taught</Label>
            <select
              id="eod_topic"
              value={topicId}
              onChange={(e) => setTopicId(e.target.value)}
              className={SELECT_CLASS}
              disabled={topicsQuery.isLoading}
            >
              <option value="">
                {topicsQuery.isLoading
                  ? "Loading topics..."
                  : topics.length === 0
                  ? "No topics for this subject — leave blank"
                  : "Select the topic taught (optional)..."}
              </option>
              {topics.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>

          {preview && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/40 px-3 py-2 text-xs">
              {preview.isLate ? (
                <Badge variant="destructive">
                  Late start · {preview.lateBy} min
                </Badge>
              ) : (
                <Badge variant="success">On time</Badge>
              )}
              {preview.durationMin !== null && (
                <span className="text-muted-foreground">
                  Duration {Math.floor(preview.durationMin / 60)}h{" "}
                  {preview.durationMin % 60}m
                </span>
              )}
            </div>
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
              {isPending ? "Saving..." : "Save actuals"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
