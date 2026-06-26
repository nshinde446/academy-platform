"use client";

import Link from "next/link";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type {
  BatchSummary,
  LectureResponse,
  SubjectSummary,
  TeacherSummary,
  TopicSummary,
} from "../_schemas/lecture";

interface LectureTableProps {
  lectures: LectureResponse[];
  batches: BatchSummary[];
  teachers: TeacherSummary[];
  subjects: SubjectSummary[];
  topics: TopicSummary[];
  /** Lecture IDs that have at least one linked LectureSession — drives
   * the "MADE UP" chip on no-show rows that were later covered. */
  coveredLectureIds?: Set<string>;
  onStart: (lecture: LectureResponse) => void;
  onComplete: (lecture: LectureResponse) => void;
  onCancel: (lecture: LectureResponse) => void;
  onDelete: (lecture: LectureResponse) => void;
  onSubstitute: (lecture: LectureResponse) => void;
  onNoShow: (lecture: LectureResponse) => void;
  onActuals: (lecture: LectureResponse) => void;
}

function formatDuration(min: number | null): string | null {
  if (min === null || min === undefined) return null;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

// Status pill derivation. Inspired by Google Classroom's mutually-exclusive
// state model — one pill per row, color tied to MEANING (teacher
// reliability problem vs. intentional decision vs. clean outcome), not raw
// severity. See docs/lectures-and-insights.md for the rationale.
type StatusTone = "success" | "secondary" | "default" | "destructive";

const NO_SHOW_REASON_PILL_LABEL: Record<string, string> = {
  TEACHER_NO_SHOW: "teacher",
  STUDENT_NO_SHOW: "students",
  EXTERNAL: "external",
  OTHER: "other",
};

function deriveStatus(
  l: LectureResponse,
  isCovered: boolean
): { label: string; tone: StatusTone; subLabel?: string } {
  const hasSub = !!l.actual_teacher_id;

  // A makeup session covered this missed lecture — overrides cancel/no-show.
  if (isCovered && (l.lecture_status === "cancelled" || l.lecture_status === "no_show")) {
    return {
      label: "Made up",
      tone: "success",
      subLabel: l.lecture_status === "cancelled" ? "was cancelled" : "was no-show",
    };
  }

  if (l.lecture_status === "no_show") {
    const reason = (l.no_show_reason ?? "OTHER").toUpperCase();
    const reasonLabel = NO_SHOW_REASON_PILL_LABEL[reason] ?? "other";
    return {
      label: `No-show · ${reasonLabel}`,
      // Only teacher-attributable no-shows surface as red — others are
      // disruptions but not teacher reliability problems.
      tone: reason === "TEACHER_NO_SHOW" ? "destructive" : "secondary",
    };
  }

  if (l.lecture_status === "cancelled") {
    // Intentional cancellation. Grey, not red — admin chose this.
    return { label: "Cancelled", tone: "secondary" };
  }

  if (l.lecture_status === "started") {
    return {
      label: "In progress",
      tone: "default",
      subLabel: hasSub ? "with substitute" : undefined,
    };
  }

  if (l.lecture_status === "paused") {
    return { label: "Paused", tone: "secondary" };
  }

  if (l.lecture_status === "completed") {
    return hasSub
      ? { label: "Completed", tone: "default", subLabel: "by substitute" }
      : { label: "Completed", tone: "success" };
  }

  if (l.lecture_status === "rescheduled") {
    return { label: "Rescheduled", tone: "secondary" };
  }

  // Default: scheduled (future / not yet started)
  return { label: "Scheduled", tone: "default" };
}

function lookup<T extends { id: string }>(list: T[], id: string | null): T | undefined {
  if (!id) return undefined;
  return list.find((x) => x.id === id);
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** A scheduled/actual window rendered as "start – end" where the date sits on
 * the start and only the time shows for the end (same-day is the norm). */
function Window({ start, end }: { start: string | null; end: string | null }) {
  if (!start) return <span className="text-muted-foreground">—</span>;
  return (
    <div className="flex flex-col leading-tight">
      <span className="whitespace-nowrap text-sm">{formatDateTime(start)}</span>
      {end && (
        <span className="whitespace-nowrap text-xs text-muted-foreground">
          → {formatTime(end)}
        </span>
      )}
    </div>
  );
}

function teacherName(t: TeacherSummary | undefined): string {
  if (!t) return "—";
  return [t.first_name, t.last_name].filter(Boolean).join(" ") || "—";
}

export function LectureTable({
  lectures,
  batches,
  teachers,
  subjects,
  topics,
  coveredLectureIds,
  onStart,
  onComplete,
  onCancel,
  onDelete,
  onSubstitute,
  onNoShow,
  onActuals,
}: LectureTableProps) {
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Batch</TableHead>
            <TableHead className="hidden sm:table-cell">Teacher</TableHead>
            <TableHead className="hidden md:table-cell">Subject</TableHead>
            <TableHead className="hidden lg:table-cell">Topic</TableHead>
            <TableHead>Scheduled</TableHead>
            <TableHead className="hidden lg:table-cell">Actual</TableHead>
            <TableHead className="hidden xl:table-cell text-right">
              Duration
            </TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {lectures.map((l) => {
            const batch = lookup(batches, l.batch_id);
            const teacher = lookup(teachers, l.teacher_id);
            const actualTeacher = lookup(teachers, l.actual_teacher_id);
            const subject = lookup(subjects, l.subject_id);
            const topic = lookup(topics, l.topic_id);
            // rescheduled is treated as scheduled for lifecycle purposes —
            // new reschedules write back as "scheduled", but legacy rows
            // with status "rescheduled" still need a path forward.
            const isScheduledLike =
              l.lecture_status === "scheduled" ||
              l.lecture_status === "rescheduled";
            const canStart = isScheduledLike;
            const canComplete =
              l.lecture_status === "started" || l.lecture_status === "paused";
            const canCancel =
              isScheduledLike ||
              l.lecture_status === "started" ||
              l.lecture_status === "paused";
            const canNoShow = isScheduledLike;
            const canSubstitute =
              l.lecture_status !== "cancelled" &&
              l.lecture_status !== "no_show";
            // End-of-day actuals can be recorded/edited anytime the class
            // happened or is still expected to (mirrors the backend guard).
            const canActuals =
              l.lecture_status !== "cancelled" &&
              l.lecture_status !== "no_show";
            const duration = formatDuration(l.actual_duration_min);

            return (
              <TableRow key={l.id}>
                <TableCell className="font-medium">
                  {batch ? batch.name : "—"}
                </TableCell>
                <TableCell className="hidden sm:table-cell">
                  {actualTeacher ? (
                    <div className="flex flex-col">
                      <span className="line-through text-muted-foreground text-xs">
                        {teacherName(teacher)}
                      </span>
                      <span className="font-medium">
                        {teacherName(actualTeacher)}
                      </span>
                      <Badge variant="secondary" className="w-fit mt-0.5 text-[10px]">
                        {l.change_reason ?? "substitute"}
                      </Badge>
                    </div>
                  ) : (
                    teacherName(teacher)
                  )}
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  {subject ? subject.name : "—"}
                </TableCell>
                <TableCell className="hidden lg:table-cell text-muted-foreground">
                  {topic ? topic.name : "—"}
                </TableCell>
                <TableCell>
                  <Window start={l.scheduled_start} end={l.scheduled_end} />
                </TableCell>
                <TableCell className="hidden lg:table-cell">
                  <Window start={l.actual_start} end={l.actual_end} />
                </TableCell>
                <TableCell className="hidden xl:table-cell text-right tabular-nums text-muted-foreground">
                  {duration ?? "—"}
                </TableCell>
                <TableCell>
                  {(() => {
                    const s = deriveStatus(
                      l,
                      coveredLectureIds?.has(l.id) ?? false
                    );
                    return (
                      <div className="flex flex-col items-start gap-0.5">
                        <Badge variant={s.tone}>{s.label}</Badge>
                        {s.subLabel && (
                          <span className="text-[10px] text-muted-foreground">
                            {s.subLabel}
                          </span>
                        )}
                        {l.late_flag === true && (
                          <span className="text-[10px] font-medium text-destructive">
                            started late
                          </span>
                        )}
                        {/* Duration shows in its own column (xl); repeat it
                            here on smaller screens where that column is hidden. */}
                        {duration && (
                          <span className="text-[10px] text-muted-foreground xl:hidden">
                            {duration}
                          </span>
                        )}
                      </div>
                    );
                  })()}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex flex-wrap justify-end gap-1">
                    {canStart && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onStart(l)}
                        aria-label={`Start lecture ${l.id}`}
                      >
                        Start
                      </Button>
                    )}
                    {canComplete && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onComplete(l)}
                        aria-label={`Complete lecture ${l.id}`}
                      >
                        Complete
                      </Button>
                    )}
                    {canCancel && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onCancel(l)}
                        aria-label={`Cancel lecture ${l.id}`}
                      >
                        Cancel
                      </Button>
                    )}
                    {canNoShow && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onNoShow(l)}
                        aria-label={`Mark no-show for lecture ${l.id}`}
                      >
                        No-Show
                      </Button>
                    )}
                    {canSubstitute && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onSubstitute(l)}
                        aria-label={`Mark substitute for lecture ${l.id}`}
                      >
                        {l.actual_teacher_id ? "Edit Sub" : "Substitute"}
                      </Button>
                    )}
                    {canActuals && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onActuals(l)}
                        aria-label={`Record end-of-day actuals for lecture ${l.id}`}
                      >
                        {l.actual_start ? "Edit Actuals" : "End of Day"}
                      </Button>
                    )}
                    <Link
                      href={`/attendance?lecture_id=${l.id}`}
                      className="inline-flex h-8 items-center rounded-md border border-input bg-background px-3 text-xs font-medium hover:bg-accent"
                      aria-label={`View attendance for lecture ${l.id}`}
                    >
                      Attendance
                    </Link>
                    <Button
                      type="button"
                      size="sm"
                      variant="destructive"
                      onClick={() => onDelete(l)}
                      aria-label={`Delete lecture ${l.id}`}
                    >
                      Delete
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
