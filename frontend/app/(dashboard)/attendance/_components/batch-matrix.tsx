"use client";

import { useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/info-hint";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useBatchMatrix } from "../_hooks/use-attendance";

const CONTROL_CLASS =
  "h-9 rounded-lg border border-input bg-background px-3 text-sm";

function localISO(d: Date): string {
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
}

function todayLocalISO(): string {
  return localISO(new Date());
}

function monthStartISO(): string {
  const d = new Date();
  return localISO(new Date(d.getFullYear(), d.getMonth(), 1));
}

// "2026-07-10" -> { day: "10", weekday: "F", title: "Fri 10 Jul 2026" }. Parse
// the parts directly so a UTC-midnight Date can't shift the day across a tz.
function dateParts(iso: string): { day: string; weekday: string; title: string } {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return {
    day: String(d).padStart(2, "0"),
    weekday: dt.toLocaleDateString(undefined, { weekday: "short" }).charAt(0),
    title: dt.toLocaleDateString(undefined, {
      weekday: "short",
      day: "2-digit",
      month: "short",
      year: "numeric",
    }),
  };
}

// Heatmap cell look per P/L/A code.
function cellClasses(code: string): string {
  switch (code) {
    case "P":
      return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300";
    case "L":
      return "bg-amber-500/15 text-amber-700 dark:text-amber-300";
    default:
      return "bg-destructive/10 text-destructive";
  }
}

function pctTone(pct: number): string {
  if (pct >= 75) return "text-emerald-600 dark:text-emerald-400";
  if (pct < 60) return "text-destructive";
  return "text-amber-600 dark:text-amber-400";
}

interface BatchMatrixProps {
  branchId: string | undefined;
  batches: { id: string; name: string }[];
}

// Whole-batch register over a range: students (rows) × working days (columns),
// each cell P/L/A, with a per-student % and a per-day present total. Surfaces
// multi-day patterns (chronic absences) that the single-day register can't.
export function BatchMatrix({ branchId, batches }: BatchMatrixProps) {
  const [batchId, setBatchId] = useState("");
  const [from, setFrom] = useState(monthStartISO());
  const [to, setTo] = useState(todayLocalISO());

  const query = useBatchMatrix(branchId, batchId || undefined, from, to);
  const matrix = query.data;
  const dates = useMemo(() => matrix?.dates ?? [], [matrix]);

  return (
    <div className="flex flex-col gap-4">
      {/* Controls */}
      <Card size="sm">
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              Batch
              <select
                value={batchId}
                onChange={(e) => setBatchId(e.target.value)}
                className={`${CONTROL_CLASS} min-w-44`}
                aria-label="Select batch"
              >
                <option value="">Select a batch…</option>
                {batches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              From
              <input
                type="date"
                value={from}
                max={to}
                onChange={(e) => setFrom(e.target.value)}
                className={CONTROL_CLASS}
                aria-label="Range start"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              To
              <input
                type="date"
                value={to}
                min={from}
                onChange={(e) => setTo(e.target.value)}
                className={CONTROL_CLASS}
                aria-label="Range end"
              />
            </label>
            <div className="flex items-center gap-1 pb-1">
              <InfoHint
                text={
                  <>
                    Every student in the batch (rows) across each working day in
                    the range (columns). P = present, L = late, A = absent. The
                    right column is each student&apos;s % for the range; the
                    bottom row is how many were present each day. Only days with
                    a scheduled lecture appear as columns.
                  </>
                }
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Matrix */}
      {!branchId ? (
        <p className="text-muted-foreground text-sm">No branch selected.</p>
      ) : !batchId ? (
        <p className="text-muted-foreground text-sm">
          Pick a batch to see its month attendance matrix.
        </p>
      ) : query.isLoading ? (
        <TableSkeleton rows={6} />
      ) : query.isError ? (
        <p className="text-destructive text-sm">Failed to load the matrix.</p>
      ) : !matrix || matrix.student_count === 0 ? (
        <p className="text-muted-foreground text-sm">
          No students enrolled in this batch yet.
        </p>
      ) : dates.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No scheduled lectures for this batch in the selected range.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border ring-1 ring-foreground/10">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b bg-muted/30">
                <th className="sticky left-0 z-10 w-24 bg-muted/30 px-3 py-2 text-left font-medium">
                  PRN
                </th>
                <th className="sticky left-24 z-10 bg-muted/30 px-3 py-2 text-left font-medium">
                  Student
                </th>
                {dates.map((d) => {
                  const p = dateParts(d);
                  return (
                    <th
                      key={d}
                      title={p.title}
                      className="w-9 px-0 py-2 text-center font-medium text-muted-foreground"
                    >
                      <div className="flex flex-col leading-tight">
                        <span className="text-[10px]">{p.weekday}</span>
                        <span className="tabular-nums">{p.day}</span>
                      </div>
                    </th>
                  );
                })}
                <th className="px-3 py-2 text-right font-medium">Absent</th>
                <th className="px-3 py-2 text-right font-medium">%</th>
              </tr>
            </thead>
            <tbody>
              {matrix.students.map((s) => (
                <tr key={s.student_id} className="border-b last:border-0">
                  <td className="sticky left-0 z-10 w-24 bg-background px-3 py-1.5 text-xs text-muted-foreground tabular-nums">
                    {s.enrollment_number || "—"}
                  </td>
                  <td className="sticky left-24 z-10 bg-background px-3 py-1.5">
                    <span className="whitespace-nowrap font-medium">{s.name}</span>
                  </td>
                  {s.cells.map((code, i) => (
                    <td key={dates[i]} className="px-0.5 py-1.5 text-center">
                      <span
                        title={`${dateParts(dates[i]).title} · ${code}`}
                        className={`inline-grid h-6 w-6 place-items-center rounded text-[11px] font-medium tabular-nums ${cellClasses(code)}`}
                      >
                        {code}
                      </span>
                    </td>
                  ))}
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-destructive">
                    {s.working_days - s.present}
                  </td>
                  <td
                    className={`px-3 py-1.5 text-right font-semibold tabular-nums ${pctTone(s.attendance_pct)}`}
                  >
                    {s.attendance_pct.toFixed(0)}%
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t bg-muted/30 text-xs text-muted-foreground">
                <td className="sticky left-0 z-10 w-24 bg-muted/30 px-3 py-2 font-medium" />
                <td className="sticky left-24 z-10 bg-muted/30 px-3 py-2 font-medium">
                  Present / {matrix.student_count}
                </td>
                {matrix.day_present.map((n, i) => (
                  <td key={dates[i]} className="px-0 py-2 text-center tabular-nums">
                    {n}
                  </td>
                ))}
                <td className="px-3 py-2" />
                <td className="px-3 py-2" />
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
