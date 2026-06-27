"use client";

import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import type {
  BatchSummary,
  LectureResponse,
  SubjectSummary,
  TeacherSummary,
} from "../_schemas/lecture";

interface CalendarWeekViewProps {
  lectures: LectureResponse[];
  batches: BatchSummary[];
  teachers: TeacherSummary[];
  subjects: SubjectSummary[];
  weekStart: Date; // Monday 00:00 local
  onPrev: () => void;
  onNext: () => void;
  onToday: () => void;
  isLoading?: boolean;
}

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function hhmm(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

// Left-border colour by lifecycle so the week reads at a glance.
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

export function CalendarWeekView({
  lectures,
  batches,
  teachers,
  subjects,
  weekStart,
  onPrev,
  onNext,
  onToday,
  isLoading,
}: CalendarWeekViewProps) {
  const days = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)),
    [weekStart],
  );

  // Bucket lectures by local calendar day, sorted by time within each day.
  const byDay = useMemo(() => {
    const map = new Map<string, LectureResponse[]>();
    for (const l of lectures) {
      const d = new Date(l.scheduled_start);
      if (Number.isNaN(d.getTime())) continue;
      const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
      const arr = map.get(key) ?? [];
      arr.push(l);
      map.set(key, arr);
    }
    for (const arr of map.values()) {
      arr.sort(
        (a, b) =>
          new Date(a.scheduled_start).getTime() -
          new Date(b.scheduled_start).getTime(),
      );
    }
    return map;
  }, [lectures]);

  const today = new Date();
  const weekEnd = addDays(weekStart, 6);
  const rangeLabel = `${weekStart.toLocaleDateString(undefined, {
    month: "short",
    day: "2-digit",
  })} – ${weekEnd.toLocaleDateString(undefined, {
    month: "short",
    day: "2-digit",
    year: "numeric",
  })}`;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onPrev}>
          ← Prev
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onToday}>
          This week
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onNext}>
          Next →
        </Button>
        <span className="ml-2 text-sm font-medium">{rangeLabel}</span>
        {isLoading && (
          <span className="text-xs text-muted-foreground">loading…</span>
        )}
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-7">
        {days.map((day, i) => {
          const key = `${day.getFullYear()}-${day.getMonth()}-${day.getDate()}`;
          const dayLectures = byDay.get(key) ?? [];
          const isToday = sameDay(day, today);
          return (
            <div
              key={key}
              className={
                "flex min-h-24 flex-col gap-1 rounded-lg border p-1.5 " +
                (isToday ? "border-primary/50 bg-primary/5" : "bg-background")
              }
              data-testid="calendar-day"
            >
              <div className="flex items-baseline justify-between px-0.5">
                <span className="text-xs font-semibold">{DAY_NAMES[i]}</span>
                <span className="text-[10px] tabular-nums text-muted-foreground">
                  {day.toLocaleDateString(undefined, {
                    month: "short",
                    day: "2-digit",
                  })}
                </span>
              </div>
              {dayLectures.length === 0 ? (
                <span className="px-0.5 text-[10px] text-muted-foreground/60">
                  —
                </span>
              ) : (
                dayLectures.map((l) => {
                  const batch = lookup(batches, l.batch_id);
                  const subject = lookup(subjects, l.subject_id);
                  const teacher = lookup(teachers, l.teacher_id);
                  return (
                    <div
                      key={l.id}
                      data-testid="calendar-lecture"
                      title={`${hhmm(l.scheduled_start)} ${batch?.name ?? ""} · ${
                        subject?.name ?? ""
                      } · ${teacher ? `${teacher.first_name} ${teacher.last_name}` : ""}`}
                      className={
                        "rounded border border-l-4 bg-card px-1.5 py-1 text-[11px] leading-tight " +
                        statusAccent(l.lecture_status)
                      }
                    >
                      <div className="font-medium tabular-nums">
                        {hhmm(l.scheduled_start)}
                      </div>
                      <div className="truncate">{batch?.name ?? "—"}</div>
                      <div className="truncate text-muted-foreground">
                        {subject?.name ?? "—"}
                        {teacher ? ` · ${teacher.first_name}` : ""}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
