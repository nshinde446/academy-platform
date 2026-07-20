"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import type {
  BatchSummary,
  ClassroomSummary,
  HolidayResponse,
  LectureResponse,
  SubjectSummary,
  TeacherLeaveResponse,
  TeacherSummary,
} from "../_schemas/lecture";

interface CalendarDayViewProps {
  lectures: LectureResponse[];
  batches: BatchSummary[];
  teachers: TeacherSummary[];
  subjects: SubjectSummary[];
  classrooms: ClassroomSummary[];
  holidays: HolidayResponse[];
  leaves: TeacherLeaveResponse[];
  day: Date; // local midnight of the day being shown
  onPrev: () => void;
  onNext: () => void;
  onToday: () => void;
  /** Click an empty slot to open the scheduler pre-filled with that window. */
  onScheduleAt?: (start: Date, end: Date) => void;
  onSelect?: (lecture: LectureResponse) => void;
  isLoading?: boolean;
}

// Agenda window. Free slots are only offered inside it; lectures outside it
// still render, they just don't generate "click to schedule" gaps.
const DAY_START_HOUR = 7;
const DAY_END_HOUR = 21;

function atHour(day: Date, hour: number): Date {
  const d = new Date(day);
  d.setHours(hour, 0, 0, 0);
  return d;
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function toDateKey(d: Date): string {
  const shifted = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 10);
}

function hhmm(d: Date): string {
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function statusAccent(status: string): string {
  switch (status) {
    case "completed":
      return "border-l-emerald-500";
    case "started":
    case "paused":
      return "border-l-amber-500";
    case "cancelled":
      return "border-l-muted-foreground/40";
    case "no_show":
      return "border-l-rose-500";
    default:
      return "border-l-blue-500"; // scheduled / rescheduled
  }
}

function lookup<T extends { id: string }>(list: T[], id: string | null) {
  if (!id) return undefined;
  return list.find((x) => x.id === id);
}

/** A lecture that no longer occupies the timetable — it frees its slot. */
function isVacated(l: LectureResponse): boolean {
  return l.lecture_status === "cancelled" || l.lecture_status === "rescheduled";
}

type Row =
  | { kind: "lecture"; key: string; start: Date; end: Date; lecture: LectureResponse }
  | { kind: "gap"; key: string; start: Date; end: Date };

/**
 * Overlap reasons between two lectures. Two lectures may legitimately share a
 * time slot (different teacher, batch and room); only a shared resource is a
 * real double-booking.
 */
function clashReasons(
  a: LectureResponse,
  b: LectureResponse,
  teachers: TeacherSummary[],
  batches: BatchSummary[],
  classrooms: ClassroomSummary[],
): string[] {
  const reasons: string[] = [];
  const aTeacher = a.actual_teacher_id ?? a.teacher_id;
  const bTeacher = b.actual_teacher_id ?? b.teacher_id;
  if (aTeacher === bTeacher) {
    const t = lookup(teachers, aTeacher);
    reasons.push(t ? `${t.first_name} ${t.last_name} is double-booked` : "Teacher is double-booked");
  }
  if (a.batch_id === b.batch_id) {
    const bt = lookup(batches, a.batch_id);
    reasons.push(bt ? `${bt.name} has two lectures at once` : "Batch has two lectures at once");
  }
  if (a.classroom_id && a.classroom_id === b.classroom_id) {
    const c = lookup(classrooms, a.classroom_id);
    reasons.push(c ? `Room ${c.code} is double-booked` : "Room is double-booked");
  }
  return reasons;
}

export function CalendarDayView({
  lectures,
  batches,
  teachers,
  subjects,
  classrooms,
  holidays,
  leaves,
  day,
  onPrev,
  onNext,
  onToday,
  onScheduleAt,
  onSelect,
  isLoading,
}: CalendarDayViewProps) {
  // "Now" marker — ticks each minute so the line drifts like a real calendar.
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  const isToday = sameDay(day, now);
  const dayKey = toDateKey(day);

  const holiday = useMemo(
    () => holidays.find((h) => h.holiday_date === dayKey),
    [holidays, dayKey],
  );

  const teachersOnLeave = useMemo(() => {
    const out: { teacher: TeacherSummary | undefined; reason: string | null }[] = [];
    for (const lv of leaves) {
      if (lv.start_date <= dayKey && dayKey <= lv.end_date) {
        out.push({ teacher: lookup(teachers, lv.teacher_id), reason: lv.reason });
      }
    }
    return out;
  }, [leaves, teachers, dayKey]);

  const leaveTeacherIds = useMemo(
    () => new Set(teachersOnLeave.map((x) => x.teacher?.id).filter(Boolean) as string[]),
    [teachersOnLeave],
  );

  // Lectures on this day, chronological.
  const dayLectures = useMemo(() => {
    return lectures
      .filter((l) => {
        const d = new Date(l.scheduled_start);
        return !Number.isNaN(d.getTime()) && sameDay(d, day);
      })
      .sort(
        (a, b) =>
          new Date(a.scheduled_start).getTime() -
          new Date(b.scheduled_start).getTime(),
      );
  }, [lectures, day]);

  // Resource clashes, computed pairwise over the day (n is small).
  const clashes = useMemo(() => {
    const map = new Map<string, string[]>();
    const live = dayLectures.filter((l) => !isVacated(l));
    for (let i = 0; i < live.length; i++) {
      for (let j = i + 1; j < live.length; j++) {
        const a = live[i];
        const b = live[j];
        const aS = new Date(a.scheduled_start).getTime();
        const aE = new Date(a.scheduled_end).getTime();
        const bS = new Date(b.scheduled_start).getTime();
        const bE = new Date(b.scheduled_end).getTime();
        if (aS >= bE || bS >= aE) continue; // no time overlap
        const reasons = clashReasons(a, b, teachers, batches, classrooms);
        if (reasons.length === 0) continue;
        map.set(a.id, [...(map.get(a.id) ?? []), ...reasons]);
        map.set(b.id, [...(map.get(b.id) ?? []), ...reasons]);
      }
    }
    return map;
  }, [dayLectures, teachers, batches, classrooms]);

  // Interleave lectures with the free gaps between them. Cancelled and
  // rescheduled lectures still render but do not block their slot, so the
  // freed time is offered back to the scheduler.
  const rows = useMemo<Row[]>(() => {
    const out: Row[] = [];
    const windowStart = atHour(day, DAY_START_HOUR);
    const windowEnd = atHour(day, DAY_END_HOUR);
    let cursor = windowStart;

    const pushGap = (from: Date, to: Date) => {
      if (to.getTime() - from.getTime() < 15 * 60_000) return; // ignore slivers
      out.push({ kind: "gap", key: `gap-${from.getTime()}`, start: from, end: to });
    };

    for (const l of dayLectures) {
      const start = new Date(l.scheduled_start);
      const end = new Date(l.scheduled_end);
      if (!isVacated(l) && start > cursor) {
        pushGap(cursor, start < windowEnd ? start : windowEnd);
      }
      out.push({ kind: "lecture", key: l.id, start, end, lecture: l });
      if (!isVacated(l) && end > cursor) cursor = end;
    }

    if (cursor < windowEnd) pushGap(cursor, windowEnd);
    return out;
  }, [dayLectures, day]);

  const dateLabel = day.toLocaleDateString(undefined, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const scheduledCount = dayLectures.filter((l) => !isVacated(l)).length;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onPrev}>
          ← Prev
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onToday}>
          Today
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onNext}>
          Next →
        </Button>
        <span className="ml-2 text-sm font-medium">{dateLabel}</span>
        <span className="text-xs text-muted-foreground">
          {scheduledCount} lecture{scheduledCount === 1 ? "" : "s"}
        </span>
        {isLoading && (
          <span className="text-xs text-muted-foreground">loading…</span>
        )}
      </div>

      {holiday && (
        <div
          data-testid="day-holiday-banner"
          className="rounded-lg border border-dashed bg-muted/50 px-3 py-2 text-sm text-muted-foreground"
        >
          <span className="font-medium text-foreground">Holiday — {holiday.name}.</span>{" "}
          Anything scheduled today is an exception.
        </div>
      )}

      {teachersOnLeave.length > 0 && (
        <div
          data-testid="day-leave-banner"
          className="rounded-lg border border-dashed bg-amber-500/5 px-3 py-2 text-sm text-muted-foreground"
        >
          <span className="font-medium text-foreground">On leave:</span>{" "}
          {teachersOnLeave
            .map((x) =>
              x.teacher
                ? `${x.teacher.first_name} ${x.teacher.last_name}${x.reason ? ` (${x.reason})` : ""}`
                : "Unknown teacher",
            )
            .join(", ")}
        </div>
      )}

      <div className="flex flex-col rounded-lg border">
        {rows.length === 0 && (
          <p className="px-3 py-6 text-center text-sm text-muted-foreground">
            Nothing scheduled today.
          </p>
        )}

        {rows.map((row, i) => {
          // The "now" line sits before the first row that starts after now.
          const showNow =
            isToday &&
            now >= (i === 0 ? new Date(0) : rows[i - 1].end) &&
            now < row.end;

          if (row.kind === "gap") {
            const label = `${hhmm(row.start)} – ${hhmm(row.end)}`;
            return (
              <div key={row.key}>
                {showNow && <NowLine now={now} />}
                <button
                  type="button"
                  data-testid="day-free-slot"
                  disabled={!onScheduleAt}
                  onClick={() => onScheduleAt?.(row.start, row.end)}
                  aria-label={`Schedule a lecture at ${label}`}
                  className="flex w-full items-center gap-3 border-b border-dashed px-3 py-2 text-left text-xs text-muted-foreground last:border-b-0 enabled:hover:bg-muted/50 disabled:cursor-default"
                >
                  <span className="w-28 shrink-0 tabular-nums">{label}</span>
                  <span className="italic">
                    {onScheduleAt ? "Free — click to schedule" : "Free"}
                  </span>
                </button>
              </div>
            );
          }

          const l = row.lecture;
          const batch = lookup(batches, l.batch_id);
          const subject = lookup(subjects, l.subject_id);
          const teacherId = l.actual_teacher_id ?? l.teacher_id;
          const teacher = lookup(teachers, teacherId);
          const classroom = lookup(classrooms, l.classroom_id);
          const rowClashes = clashes.get(l.id) ?? [];
          const vacated = isVacated(l);
          const teacherAway = leaveTeacherIds.has(teacherId) && !vacated;

          return (
            <div key={row.key}>
              {showNow && <NowLine now={now} />}
              <div
                data-testid="day-lecture"
                role={onSelect ? "button" : undefined}
                tabIndex={onSelect ? 0 : undefined}
                onClick={onSelect ? () => onSelect(l) : undefined}
                onKeyDown={
                  onSelect
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onSelect(l);
                        }
                      }
                    : undefined
                }
                className={
                  "flex flex-col gap-1 border-b border-l-4 px-3 py-2 last:border-b-0 sm:flex-row sm:items-center sm:gap-3 " +
                  statusAccent(l.lecture_status) +
                  (vacated ? " opacity-50" : "") +
                  (onSelect ? " cursor-pointer hover:bg-muted/40" : "")
                }
              >
                <span className="w-28 shrink-0 text-xs tabular-nums text-muted-foreground">
                  {hhmm(row.start)} – {hhmm(row.end)}
                </span>
                <span className="flex-1 text-sm">
                  <span className="font-medium">{subject?.name ?? "—"}</span>
                  <span className="text-muted-foreground">
                    {" · "}
                    {batch?.name ?? "—"}
                    {teacher ? ` · ${teacher.first_name} ${teacher.last_name}` : ""}
                    {classroom ? ` · ${classroom.code}` : ""}
                  </span>
                </span>
                <span className="flex flex-wrap items-center gap-1.5">
                  {l.actual_teacher_id &&
                    l.actual_teacher_id !== l.teacher_id && (
                      <Badge tone="info">Substitute</Badge>
                    )}
                  {teacherAway && <Badge tone="warn">Teacher on leave</Badge>}
                  {rowClashes.length > 0 && (
                    <Badge tone="danger" title={rowClashes.join("; ")}>
                      Conflict
                    </Badge>
                  )}
                  <Badge tone="muted">{l.lecture_status.replace("_", " ")}</Badge>
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function NowLine({ now }: { now: Date }) {
  return (
    <div
      data-testid="day-now-line"
      aria-hidden
      className="flex items-center gap-2 px-3"
    >
      <span className="text-[10px] font-medium tabular-nums text-rose-500">
        {hhmm(now)}
      </span>
      <span className="h-px flex-1 bg-rose-500" />
      <span className="size-1.5 rounded-full bg-rose-500" />
    </div>
  );
}

function Badge({
  tone,
  title,
  children,
}: {
  tone: "info" | "warn" | "danger" | "muted";
  title?: string;
  children: React.ReactNode;
}) {
  const cls = {
    info: "border-blue-500/40 text-blue-600 dark:text-blue-400",
    warn: "border-amber-500/40 text-amber-600 dark:text-amber-400",
    danger: "border-rose-500/40 text-rose-600 dark:text-rose-400",
    muted: "border-border text-muted-foreground",
  }[tone];
  return (
    <span
      title={title}
      className={`rounded border px-1.5 py-0.5 text-[10px] font-medium capitalize ${cls}`}
    >
      {children}
    </span>
  );
}
