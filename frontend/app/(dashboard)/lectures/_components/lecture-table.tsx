"use client";

import { useMemo, useState } from "react";
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
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import type {
  BatchSummary,
  ClassroomSummary,
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
  classrooms?: ClassroomSummary[];
  /** Lecture IDs that have at least one linked LectureSession — drives
   * the "MADE UP" chip on no-show rows that were later covered. */
  coveredLectureIds?: Set<string>;
  /** Row selection (for "copy selected to date"). When provided, a checkbox
   * column is rendered. */
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
  onToggleAll?: (checked: boolean) => void;
  onStart: (lecture: LectureResponse) => void;
  onComplete: (lecture: LectureResponse) => void;
  onCancel: (lecture: LectureResponse) => void;
  onDelete: (lecture: LectureResponse) => void;
  onSubstitute: (lecture: LectureResponse) => void;
  onNoShow: (lecture: LectureResponse) => void;
  onActuals: (lecture: LectureResponse) => void;
  onGenerateDpp?: (lecture: LectureResponse) => void;
  onRecordMakeup?: (lecture: LectureResponse) => void;
  onReschedule?: (lecture: LectureResponse) => void;
}

function formatDuration(min: number | null): string | null {
  if (min === null || min === undefined) return null;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

// Stable colour per subject from a small palette, hashed by code/name — the
// same subject always reads the same colour (the design's SubjectTag).
const SUBJECT_PALETTE = [
  "bg-blue-500/15 text-blue-700 dark:text-blue-300",
  "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  "bg-violet-500/15 text-violet-700 dark:text-violet-300",
  "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  "bg-rose-500/15 text-rose-700 dark:text-rose-300",
  "bg-cyan-500/15 text-cyan-700 dark:text-cyan-300",
];
function subjectColor(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) | 0;
  return SUBJECT_PALETTE[Math.abs(h) % SUBJECT_PALETTE.length];
}
function SubjectTag({ subject }: { subject: SubjectSummary | undefined }) {
  if (!subject) return <span className="text-muted-foreground">—</span>;
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium ${subjectColor(
        subject.code || subject.name,
      )}`}
    >
      {subject.name}
    </span>
  );
}

// Compact "Jun 26 · 09:00" for the schedule cell (the design's "When").
function compactWhen(iso: string): { day: string; time: string } {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { day: iso, time: "" };
  return {
    day: d.toLocaleDateString(undefined, { month: "short", day: "2-digit" }),
    time: d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    }),
  };
}

// Status pill derivation. Inspired by Google Classroom's mutually-exclusive
// state model — one pill per row, color tied to MEANING (teacher
// reliability problem vs. intentional decision vs. clean outcome), not raw
// severity. See docs/lectures-and-insights.md for the rationale.
type StatusTone = "success" | "secondary" | "default" | "destructive";

// Leading dot colour per status tone (the design's dotted status badge).
const DOT_COLOR: Record<StatusTone, string> = {
  success: "bg-emerald-500",
  destructive: "bg-rose-500",
  secondary: "bg-muted-foreground/50",
  default: "bg-blue-500",
};

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

/** True when the ISO timestamp falls on a calendar day after today (local) —
 * used to hide "end of day" actuals on lectures that haven't happened yet. */
function isFutureDay(iso: string): boolean {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const day = new Date(d);
  day.setHours(0, 0, 0, 0);
  return day.getTime() > today.getTime();
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

type SortKey =
  | "batch"
  | "teacher"
  | "subject"
  | "scheduled"
  | "duration"
  | "status";
type SortDir = "asc" | "desc";

function sortValue(
  l: LectureResponse,
  key: SortKey,
  batches: BatchSummary[],
  teachers: TeacherSummary[],
  subjects: SubjectSummary[],
): string | number {
  switch (key) {
    case "batch":
      return (lookup(batches, l.batch_id)?.name ?? "").toLowerCase();
    case "teacher":
      return teacherName(lookup(teachers, l.teacher_id)).toLowerCase();
    case "subject":
      return (lookup(subjects, l.subject_id)?.name ?? "").toLowerCase();
    case "scheduled":
      return new Date(l.scheduled_start).getTime() || 0;
    case "duration":
      return l.actual_duration_min ?? -1; // un-timed rows sort last (asc)
    case "status":
      return l.lecture_status;
  }
}

export function LectureTable({
  lectures,
  batches,
  teachers,
  subjects,
  topics,
  classrooms = [],
  coveredLectureIds,
  selectedIds,
  onToggleSelect,
  onToggleAll,
  onStart,
  onComplete,
  onCancel,
  onDelete,
  onSubstitute,
  onNoShow,
  onActuals,
  onGenerateDpp,
  onRecordMakeup,
  onReschedule,
}: LectureTableProps) {
  const selectable = !!selectedIds && !!onToggleSelect;
  const allSelected =
    selectable &&
    lectures.length > 0 &&
    lectures.every((l) => selectedIds!.has(l.id));

  // Column sort — defaults to scheduled time, newest first (the backend order).
  const [sortKey, setSortKey] = useState<SortKey>("scheduled");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("asc");
    }
  }
  const sorted = useMemo(() => {
    const arr = [...lectures];
    arr.sort((a, b) => {
      const va = sortValue(a, sortKey, batches, teachers, subjects);
      const vb = sortValue(b, sortKey, batches, teachers, subjects);
      let c = 0;
      if (typeof va === "number" && typeof vb === "number") c = va - vb;
      else c = String(va).localeCompare(String(vb));
      return sortDir === "asc" ? c : -c;
    });
    return arr;
  }, [lectures, sortKey, sortDir, batches, teachers, subjects]);

  function SortHead({
    label,
    sortKey: key,
    className,
  }: {
    label: string;
    sortKey: SortKey;
    className?: string;
  }) {
    const active = sortKey === key;
    return (
      <TableHead className={className}>
        <button
          type="button"
          onClick={() => toggleSort(key)}
          className="inline-flex items-center gap-1 font-medium hover:text-foreground"
          aria-label={`Sort by ${label}`}
        >
          {label}
          <span className="text-[10px] text-muted-foreground">
            {active ? (sortDir === "asc" ? "▲" : "▼") : "↕"}
          </span>
        </button>
      </TableHead>
    );
  }

  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            {selectable && (
              <TableHead className="w-10">
                <input
                  type="checkbox"
                  aria-label="Select all lectures"
                  checked={allSelected}
                  onChange={(e) => onToggleAll?.(e.target.checked)}
                  className="h-4 w-4 rounded border-input"
                />
              </TableHead>
            )}
            <SortHead label="Batch" sortKey="batch" />
            <SortHead
              label="Teacher"
              sortKey="teacher"
              className="hidden sm:table-cell"
            />
            <SortHead
              label="Subject"
              sortKey="subject"
              className="hidden md:table-cell"
            />
            <TableHead className="hidden lg:table-cell">Topic</TableHead>
            <TableHead className="hidden xl:table-cell">Room</TableHead>
            <SortHead label="Scheduled" sortKey="scheduled" />
            <TableHead className="hidden lg:table-cell">Actual</TableHead>
            <SortHead
              label="Duration"
              sortKey="duration"
              className="hidden xl:table-cell text-right"
            />
            <SortHead label="Status" sortKey="status" />
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((l) => {
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
            // Only a not-yet-started lecture can be moved to a new time.
            const canReschedule = isScheduledLike;
            const canSubstitute =
              l.lecture_status !== "cancelled" &&
              l.lecture_status !== "no_show";
            // The actuals/plan action is available on any non-terminal lecture.
            // For a future-scheduled lecture it opens in topic-only "plan" mode
            // (set what will be taught); actuals/completion stay blocked until
            // the day (mirrors the backend guard).
            const canActuals =
              l.lecture_status !== "cancelled" &&
              l.lecture_status !== "no_show";
            const isFuture = isFutureDay(l.scheduled_start);
            const duration = formatDuration(l.actual_duration_min);
            const classroom = lookup(classrooms, l.classroom_id);

            // Primary "quick action" (the reference design): the single most
            // likely next action, by status. Everything else lives in the ⋯
            // overflow, which excludes whatever is shown here.
            const st = l.lecture_status;
            let primary:
              | { key: string; label: string; onClick: () => void; variant: "default" | "outline" }
              | null = null;
            if (st === "completed" && onGenerateDpp) {
              primary = { key: "dpp", label: "✦ Generate DPP", onClick: () => onGenerateDpp(l), variant: "outline" };
            } else if (canComplete) {
              primary = { key: "complete", label: "Complete", onClick: () => onComplete(l), variant: "default" };
            } else if ((st === "cancelled" || st === "no_show") && onRecordMakeup) {
              primary = { key: "makeup", label: "Record makeup", onClick: () => onRecordMakeup(l), variant: "outline" };
            } else if (isScheduledLike) {
              primary = isFuture
                ? { key: "plan", label: "Plan topic", onClick: () => onActuals(l), variant: "outline" }
                : { key: "start", label: "Start", onClick: () => onStart(l), variant: "default" };
            }

            return (
              <TableRow key={l.id}>
                {selectable && (
                  <TableCell className="w-10">
                    <input
                      type="checkbox"
                      aria-label={`Select lecture ${l.id}`}
                      checked={selectedIds!.has(l.id)}
                      onChange={() => onToggleSelect!(l.id)}
                      className="h-4 w-4 rounded border-input"
                    />
                  </TableCell>
                )}
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
                  <SubjectTag subject={subject} />
                </TableCell>
                <TableCell className="hidden lg:table-cell text-muted-foreground">
                  {topic ? topic.name : "—"}
                </TableCell>
                <TableCell className="hidden xl:table-cell text-xs text-muted-foreground">
                  {classroom ? classroom.name : "—"}
                </TableCell>
                <TableCell>
                  {(() => {
                    const w = compactWhen(l.scheduled_start);
                    const end = compactWhen(l.scheduled_end);
                    return (
                      <div className="flex flex-col leading-tight">
                        <span className="whitespace-nowrap text-sm tabular-nums">
                          {w.day} · {w.time}
                        </span>
                        {end.time && (
                          <span className="text-[10px] text-muted-foreground tabular-nums">
                            → {end.time}
                          </span>
                        )}
                      </div>
                    );
                  })()}
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
                        <Badge variant={s.tone} className="gap-1.5">
                          <span
                            aria-hidden
                            className={`inline-block h-1.5 w-1.5 rounded-full ${DOT_COLOR[s.tone]}`}
                          />
                          {s.label}
                        </Badge>
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
                  <div className="flex items-center justify-end gap-1">
                    {primary && (
                      <Button
                        type="button"
                        size="sm"
                        variant={primary.variant}
                        onClick={primary.onClick}
                        className="whitespace-nowrap"
                      >
                        {primary.label}
                      </Button>
                    )}
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        render={
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            aria-label={`More actions for lecture ${l.id}`}
                            className="px-2"
                          >
                            <span aria-hidden className="text-base leading-none">
                              ⋯
                            </span>
                          </Button>
                        }
                      />
                      <DropdownMenuContent>
                        {canStart && primary?.key !== "start" && (
                          <DropdownMenuItem onClick={() => onStart(l)}>
                            Start
                          </DropdownMenuItem>
                        )}
                        {canComplete && primary?.key !== "complete" && (
                          <DropdownMenuItem onClick={() => onComplete(l)}>
                            Complete
                          </DropdownMenuItem>
                        )}
                        {canActuals && primary?.key !== "plan" && (
                          <DropdownMenuItem onClick={() => onActuals(l)}>
                            {isFuture
                              ? "Plan topic"
                              : l.actual_start
                                ? "Edit actuals"
                                : "End of day"}
                          </DropdownMenuItem>
                        )}
                        {canSubstitute && (
                          <DropdownMenuItem onClick={() => onSubstitute(l)}>
                            {l.actual_teacher_id ? "Edit substitute" : "Substitute"}
                          </DropdownMenuItem>
                        )}
                        {canReschedule && onReschedule && (
                          <DropdownMenuItem onClick={() => onReschedule(l)}>
                            Reschedule
                          </DropdownMenuItem>
                        )}
                        {canNoShow && (
                          <DropdownMenuItem onClick={() => onNoShow(l)}>
                            Mark no-show
                          </DropdownMenuItem>
                        )}
                        {canCancel && (
                          <DropdownMenuItem onClick={() => onCancel(l)}>
                            Cancel
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          render={<Link href={`/attendance?lecture_id=${l.id}`} />}
                        >
                          Attendance
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => onDelete(l)}
                      aria-label={`Delete lecture ${l.id}`}
                      className="px-2 text-destructive hover:bg-destructive/10 hover:text-destructive"
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
