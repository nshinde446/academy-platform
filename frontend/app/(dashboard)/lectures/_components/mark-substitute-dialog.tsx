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
import type {
  ChangeReason,
  LectureResponse,
  LectureSubstitute,
  TeacherSummary,
} from "../_schemas/lecture";

interface MarkSubstituteDialogProps {
  lecture: LectureResponse | null;
  teachers: TeacherSummary[];
  /** Optional: pass all branch lectures to enable smart substitute
   * suggestions (subject experience, topic experience, free slot). */
  allLectures?: LectureResponse[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: LectureSubstitute) => Promise<void> | void;
  isPending: boolean;
}

interface RankedTeacher {
  teacher: TeacherSummary;
  score: number;
  reasons: string[];
}

/** Rank candidate substitute teachers using existing lecture history.
 *
 *   +30  has taught this subject (completed lecture as scheduled OR
 *        actual teacher) — biggest single signal
 *   +20  has taught this exact topic before
 *   +10  free at this time slot (no overlapping lecture)
 *   -5   recently overloaded as substitute (≥3 sub-ins in last 30 days)
 *
 * Zero-score teachers still appear in the picker, just below the
 * "Suggested" group.
 */
function rankCandidates(
  lecture: LectureResponse,
  candidates: TeacherSummary[],
  allLectures: LectureResponse[],
): RankedTeacher[] {
  const start = new Date(lecture.scheduled_start).getTime();
  const end = new Date(lecture.scheduled_end).getTime();
  const thirtyDaysAgo = Date.now() - 30 * 24 * 60 * 60 * 1000;

  return candidates.map((t) => {
    let score = 0;
    const reasons: string[] = [];

    const taughtSubject = allLectures.some(
      (l) =>
        l.subject_id === lecture.subject_id &&
        l.lecture_status === "completed" &&
        (l.teacher_id === t.id || l.actual_teacher_id === t.id),
    );
    if (taughtSubject) {
      score += 30;
      reasons.push("subject experience");
    }

    if (lecture.topic_id) {
      const taughtTopic = allLectures.some(
        (l) =>
          l.topic_id === lecture.topic_id &&
          l.lecture_status === "completed" &&
          (l.teacher_id === t.id || l.actual_teacher_id === t.id),
      );
      if (taughtTopic) {
        score += 20;
        reasons.push("topic experience");
      }
    }

    const hasConflict = allLectures.some((l) => {
      if (l.id === lecture.id) return false;
      if (l.teacher_id !== t.id && l.actual_teacher_id !== t.id) return false;
      if (l.lecture_status === "cancelled" || l.lecture_status === "no_show") {
        return false;
      }
      const ls = new Date(l.scheduled_start).getTime();
      const le = new Date(l.scheduled_end).getTime();
      return ls < end && le > start;
    });
    if (!hasConflict) {
      score += 10;
      reasons.push("free this slot");
    } else {
      reasons.push("conflict — busy at this time");
    }

    const recentSubLoad = allLectures.filter(
      (l) =>
        l.actual_teacher_id === t.id &&
        new Date(l.scheduled_start).getTime() >= thirtyDaysAgo,
    ).length;
    if (recentSubLoad >= 3) {
      score -= 5;
      reasons.push(`already covered ${recentSubLoad} lectures this month`);
    }

    return { teacher: t, score, reasons };
  });
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
  allLectures,
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

  // Smart ranking. Empty allLectures = fall back to alphabetical (no
  // signals available). Otherwise rank, then group suggested above the
  // rest so the dropdown order itself encodes the recommendation.
  const ranked = useMemo<RankedTeacher[]>(() => {
    if (!lecture) return [];
    const candidates = teachers.filter((t) => t.id !== lecture.teacher_id);
    if (!allLectures || allLectures.length === 0) {
      return candidates.map((t) => ({ teacher: t, score: 0, reasons: [] }));
    }
    return rankCandidates(lecture, candidates, allLectures).sort(
      (a, b) => b.score - a.score,
    );
  }, [lecture, teachers, allLectures]);

  const suggested = ranked.filter((r) => r.score > 0);
  const others = ranked.filter((r) => r.score <= 0);
  const selectedRank = ranked.find((r) => r.teacher.id === actualTeacherId);

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
              {suggested.length > 0 && (
                <optgroup label="Suggested">
                  {suggested.map((r) => (
                    <option key={r.teacher.id} value={r.teacher.id}>
                      {teacherName(r.teacher)}
                      {" — "}
                      {r.reasons
                        .filter((x) => !x.startsWith("conflict"))
                        .slice(0, 2)
                        .join(", ")}
                    </option>
                  ))}
                </optgroup>
              )}
              {others.length > 0 && (
                <optgroup
                  label={
                    suggested.length > 0 ? "All other teachers" : "Teachers"
                  }
                >
                  {others.map((r) => (
                    <option key={r.teacher.id} value={r.teacher.id}>
                      {teacherName(r.teacher)}
                      {r.reasons.some((x) => x.startsWith("conflict"))
                        ? " — busy"
                        : ""}
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
            {selectedRank && selectedRank.reasons.length > 0 && (
              <p className="text-[10px] text-muted-foreground">
                {selectedRank.reasons.join(" · ")}
              </p>
            )}
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
