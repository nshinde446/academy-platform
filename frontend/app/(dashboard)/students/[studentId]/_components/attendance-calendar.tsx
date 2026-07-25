"use client";

import { useMemo, useState } from "react";
import {
  useAttendanceSummary,
  useStudentTimeline,
} from "../../../attendance/_hooks/use-attendance";
import type {
  DailyAttendance,
  DayStatus,
} from "../../../attendance/_schemas/attendance";
import { Badge } from "@/components/ui/badge";
import { InfoHint } from "@/components/ui/info-hint";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

// Local YYYY-MM-DD — the day rows are keyed on the branch's local date, so we
// bucket in local time rather than UTC to keep a punch on the day it happened.
function ymd(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function hhmm(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

// On-campus window length from sign-in to sign-out. Only meaningful when both
// punches exist; a missing sign-off (still on campus / never punched out) has no
// bounded duration, so we render a dash rather than guess.
function durationOf(first_in: string | null, last_out: string | null): string {
  if (!first_in || !last_out) return "—";
  const a = new Date(first_in).getTime();
  const b = new Date(last_out).getTime();
  if (Number.isNaN(a) || Number.isNaN(b) || b <= a) return "—";
  const mins = Math.round((b - a) / 60000);
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}h${String(m).padStart(2, "0")}`;
}

const WEEKDAYS = ["M", "T", "W", "T", "F", "S", "S"];

// One heatmap cell's look, keyed on the day's status. No row for a date means
// "no working day / no data" — a neutral cell, never counted as absent here.
function cellClasses(status: DayStatus | null): string {
  switch (status) {
    case "PRESENT":
      return "bg-emerald-500/15 text-emerald-700 ring-emerald-500/30 dark:text-emerald-300";
    case "LATE":
      return "bg-amber-500/15 text-amber-700 ring-amber-500/30 dark:text-amber-300";
    case "ABSENT":
      return "bg-destructive/10 text-destructive ring-destructive/30";
    default:
      return "bg-muted/40 text-muted-foreground ring-transparent";
  }
}

function summaryTone(pct: number): string {
  if (pct >= 75) return "text-emerald-600 dark:text-emerald-400";
  if (pct < 60) return "text-destructive";
  return "text-amber-600 dark:text-amber-400";
}

type ViewMode = "calendar" | "log";

export function StudentAttendanceCalendar({
  branchId,
  studentId,
}: {
  branchId: string | undefined;
  studentId: string;
}) {
  // Month currently in view, pinned to the 1st. Defaults to this month.
  const [anchor, setAnchor] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  // Heatmap grid (pattern-at-a-glance) vs. day-wise IN/OUT log (review every
  // sign-in / sign-out without hovering). Both are scoped to the same month.
  const [mode, setMode] = useState<ViewMode>("calendar");

  const { start, end, monthLabel, atCurrentMonth } = useMemo(() => {
    const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const last = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
    const now = new Date();
    return {
      start: ymd(first),
      end: ymd(last),
      monthLabel: first.toLocaleDateString(undefined, {
        month: "long",
        year: "numeric",
      }),
      atCurrentMonth:
        anchor.getFullYear() === now.getFullYear() &&
        anchor.getMonth() === now.getMonth(),
    };
  }, [anchor]);

  const timelineQuery = useStudentTimeline(branchId, studentId, start, end);
  const summaryQuery = useAttendanceSummary(branchId, studentId, start, end);

  // date -> day row, for O(1) cell lookup.
  const byDate = useMemo(() => {
    const map = new Map<string, DailyAttendance>();
    const rows = timelineQuery.data ?? [];
    for (const r of rows) map.set(r.attendance_date, r);
    return map;
  }, [timelineQuery.data]);

  // Calendar cells: Monday-start, leading blanks to align the 1st.
  const cells = useMemo(() => {
    const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const daysInMonth = new Date(
      anchor.getFullYear(),
      anchor.getMonth() + 1,
      0,
    ).getDate();
    const leadBlanks = (first.getDay() + 6) % 7; // Mon=0 … Sun=6
    const out: (number | null)[] = Array.from({ length: leadBlanks }, () => null);
    for (let d = 1; d <= daysInMonth; d++) out.push(d);
    return out;
  }, [anchor]);

  // Log rows: the month's day records newest-first (backend already sorts desc).
  const logRows = useMemo(
    () => timelineQuery.data ?? [],
    [timelineQuery.data],
  );

  const summary = summaryQuery.data;
  const monthYear = { y: anchor.getFullYear(), m: anchor.getMonth() };

  function step(delta: number) {
    setAnchor((a) => new Date(a.getFullYear(), a.getMonth() + delta, 1));
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-lg font-semibold">Attendance</h3>
        <InfoHint
          text={
            <>
              Whole-day campus presence from the biometric register — the
              canonical source for the attendance %. The <b>calendar</b> shows
              the month at a glance (green = present, amber = late, red = absent,
              grey = no scheduled day); the <b>log</b> lists every day&apos;s
              exact sign-in / sign-out and on-campus window.
            </>
          }
        />
        <div className="ml-auto">
          <ViewToggle mode={mode} onChange={setMode} />
        </div>
      </div>

      <div className="rounded-xl border p-3 ring-1 ring-foreground/10 sm:p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Previous month"
              onClick={() => step(-1)}
              className="grid h-8 w-8 place-items-center rounded-md border border-border text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              ‹
            </button>
            <span className="min-w-[9rem] text-center text-sm font-medium tabular-nums">
              {monthLabel}
            </span>
            <button
              type="button"
              aria-label="Next month"
              onClick={() => step(1)}
              disabled={atCurrentMonth}
              className="grid h-8 w-8 place-items-center rounded-md border border-border text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
            >
              ›
            </button>
          </div>
          {summaryQuery.isLoading ? (
            <Skeleton className="h-5 w-28" />
          ) : summary && summary.working_days > 0 ? (
            <div className="text-right text-sm">
              <span
                className={`font-semibold tabular-nums ${summaryTone(summary.attendance_pct)}`}
              >
                {summary.attendance_pct.toFixed(0)}%
              </span>
              <span className="ml-2 text-xs text-muted-foreground">
                {summary.present_days}/{summary.working_days} days
              </span>
            </div>
          ) : (
            <span className="text-xs text-muted-foreground">
              No working days
            </span>
          )}
        </div>

        {mode === "calendar" ? (
          <CalendarGrid
            cells={cells}
            monthYear={monthYear}
            byDate={byDate}
            isLoading={timelineQuery.isLoading}
          />
        ) : (
          <DayLog rows={logRows} isLoading={timelineQuery.isLoading} />
        )}
      </div>
    </div>
  );
}

function ViewToggle({
  mode,
  onChange,
}: {
  mode: ViewMode;
  onChange: (m: ViewMode) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Attendance view"
      className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5"
    >
      {(["calendar", "log"] as const).map((m) => (
        <button
          key={m}
          type="button"
          aria-pressed={mode === m}
          onClick={() => onChange(m)}
          className={cn(
            "rounded-md px-2.5 py-1 text-xs font-medium capitalize transition-colors",
            mode === m
              ? "bg-background text-foreground shadow-sm ring-1 ring-foreground/10"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {m}
        </button>
      ))}
    </div>
  );
}

function CalendarGrid({
  cells,
  monthYear,
  byDate,
  isLoading,
}: {
  cells: (number | null)[];
  monthYear: { y: number; m: number };
  byDate: Map<string, DailyAttendance>;
  isLoading: boolean;
}) {
  return (
    <>
      <div className="grid grid-cols-7 gap-1">
        {WEEKDAYS.map((w, i) => (
          <div
            key={i}
            className="pb-1 text-center text-[10px] font-medium uppercase text-muted-foreground"
          >
            {w}
          </div>
        ))}
        {isLoading
          ? Array.from({ length: 35 }, (_, i) => (
              <Skeleton key={i} className="aspect-square w-full rounded-md" />
            ))
          : cells.map((day, i) => {
              if (day == null) return <div key={i} />;
              const key = ymd(new Date(monthYear.y, monthYear.m, day));
              const row = byDate.get(key);
              const status = row?.day_status ?? null;
              const title =
                status == null
                  ? `${key} · no record`
                  : `${key} · ${status}` +
                    (status !== "ABSENT"
                      ? ` · in ${hhmm(row?.first_in ?? null)} · out ${hhmm(row?.last_out ?? null)}`
                      : "");
              return (
                <div
                  key={i}
                  title={title}
                  className={`grid aspect-square w-full place-items-center rounded-md text-xs font-medium tabular-nums ring-1 ${cellClasses(status)}`}
                >
                  {day}
                </div>
              );
            })}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
        <LegendSwatch className="bg-emerald-500/15 ring-emerald-500/30" label="Present" />
        <LegendSwatch className="bg-amber-500/15 ring-amber-500/30" label="Late" />
        <LegendSwatch className="bg-destructive/10 ring-destructive/30" label="Absent" />
        <LegendSwatch className="bg-muted/40 ring-transparent" label="No day" />
      </div>
    </>
  );
}

function dayName(dateISO: string): string {
  const d = new Date(`${dateISO}T00:00:00`);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleDateString(undefined, { weekday: "short" });
}

function dateLabel(dateISO: string): string {
  const d = new Date(`${dateISO}T00:00:00`);
  return Number.isNaN(d.getTime())
    ? dateISO
    : d.toLocaleDateString(undefined, {
        day: "2-digit",
        month: "short",
        year: "2-digit",
      });
}

// Day-wise IN/OUT roster for the student — every scheduled day in the month,
// newest first, with the exact sign-in / sign-out window. The whole month is
// visible without hovering, so it can be reviewed completely.
function DayLog({
  rows,
  isLoading,
}: {
  rows: DailyAttendance[];
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-9 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        No attendance records for this month.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
            <th className="py-2 pr-3 font-medium">Date</th>
            <th className="py-2 pr-3 font-medium">Day</th>
            <th className="py-2 pr-3 font-medium">In</th>
            <th className="py-2 pr-3 font-medium">Out</th>
            <th className="py-2 pr-3 font-medium">Hrs</th>
            <th className="py-2 pr-3 font-medium">Status</th>
            <th className="py-2 font-medium">Sign-off</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const absent = r.day_status === "ABSENT";
            return (
              <tr
                key={r.id}
                className="border-b border-border/60 last:border-0"
              >
                <td className="py-2 pr-3 font-medium tabular-nums whitespace-nowrap">
                  {dateLabel(r.attendance_date)}
                </td>
                <td className="py-2 pr-3 text-muted-foreground">
                  {dayName(r.attendance_date)}
                </td>
                <td className="py-2 pr-3 tabular-nums">
                  {hhmm(r.first_in)}
                </td>
                <td className="py-2 pr-3 tabular-nums">
                  {hhmm(r.last_out)}
                  {r.signoff === "MISSING" && (
                    <span
                      className="ml-1 text-amber-600 dark:text-amber-500"
                      title="Punched in, never punched out"
                    >
                      ⚠
                    </span>
                  )}
                </td>
                <td className="py-2 pr-3 tabular-nums text-muted-foreground">
                  {durationOf(r.first_in, r.last_out)}
                </td>
                <td className="py-2 pr-3">
                  {absent ? (
                    <Badge variant="destructive">Absent</Badge>
                  ) : (
                    <Badge
                      variant={r.day_status === "LATE" ? "warning" : "success"}
                    >
                      {r.day_status === "LATE" ? "Late" : "Present"}
                    </Badge>
                  )}
                </td>
                <td className="py-2 text-xs text-muted-foreground">
                  {r.signoff === "COMPLETE"
                    ? "Complete"
                    : r.signoff === "MISSING"
                      ? "Missing"
                      : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function LegendSwatch({
  className,
  label,
}: {
  className: string;
  label: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-3 w-3 rounded-sm ring-1 ${className}`} />
      {label}
    </span>
  );
}
