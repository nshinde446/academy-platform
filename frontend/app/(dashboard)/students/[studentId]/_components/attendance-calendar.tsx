"use client";

import { useMemo, useState } from "react";
import {
  useAttendanceSummary,
  useStudentTimeline,
} from "../../../attendance/_hooks/use-attendance";
import type { DayStatus } from "../../../attendance/_schemas/attendance";
import { InfoHint } from "@/components/ui/info-hint";
import { Skeleton } from "@/components/ui/skeleton";

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
    const map = new Map<string, (typeof rows)[number]>();
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

  const summary = summaryQuery.data;
  const monthYear = { y: anchor.getFullYear(), m: anchor.getMonth() };

  function step(delta: number) {
    setAnchor((a) => new Date(a.getFullYear(), a.getMonth() + delta, 1));
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-lg font-semibold">Attendance calendar</h3>
        <InfoHint
          text={
            <>
              Whole-day campus presence from the biometric register — the
              canonical source for the attendance %. Green = present, amber =
              late arrival, red = absent, grey = no scheduled day. Hover a day
              for the sign-in / sign-out times.
            </>
          }
        />
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

        <div className="grid grid-cols-7 gap-1">
          {WEEKDAYS.map((w, i) => (
            <div
              key={i}
              className="pb-1 text-center text-[10px] font-medium uppercase text-muted-foreground"
            >
              {w}
            </div>
          ))}
          {timelineQuery.isLoading
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
      </div>
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
