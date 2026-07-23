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
import { Card, CardContent } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/info-hint";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useDefaulters } from "../_hooks/use-attendance";
import type { DefaulterRow } from "../_schemas/attendance";

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

function pctTone(pct: number): string {
  if (pct < 50) return "text-destructive";
  return "text-amber-600 dark:text-amber-400";
}

interface DefaulterBoardProps {
  branchId: string | undefined;
}

// Institute-wide list of students below the attendance threshold over a range,
// worst-first — the eligibility (75%) follow-up surface. Each row links to the
// student's detail page (its month heatmap) so staff can act on it.
export function DefaulterBoard({ branchId }: DefaulterBoardProps) {
  const [from, setFrom] = useState(monthStartISO());
  const [to, setTo] = useState(todayLocalISO());
  const [threshold, setThreshold] = useState(75);

  const query = useDefaulters(branchId, from, to, threshold);
  const rows = useMemo<DefaulterRow[]>(() => query.data ?? [], [query.data]);

  return (
    <div className="flex flex-col gap-4">
      {/* Controls */}
      <Card size="sm">
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
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
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              Below&nbsp;%
              <select
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className={CONTROL_CLASS}
                aria-label="Attendance threshold"
              >
                {[90, 75, 60, 50, 40].map((t) => (
                  <option key={t} value={t}>
                    {t}%
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-center gap-1 pb-1">
              <span className="text-sm text-muted-foreground">
                {query.isLoading
                  ? "Loading…"
                  : `${rows.length} student${rows.length === 1 ? "" : "s"} below ${threshold}%`}
              </span>
              <InfoHint
                text={
                  <>
                    Students whose attendance over this range is below the
                    threshold, aggregated across all their batches, worst first.
                    Attendance % = present working days ÷ working days, where a
                    working day is any day with a scheduled lecture. Use this for
                    the board-eligibility (75%) follow-up.
                  </>
                }
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Board */}
      {!branchId ? (
        <p className="text-muted-foreground text-sm">No branch selected.</p>
      ) : query.isLoading ? (
        <TableSkeleton rows={6} />
      ) : query.isError ? (
        <p className="text-destructive text-sm">Failed to load defaulters.</p>
      ) : rows.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No students below {threshold}% in this range. 🎉
        </p>
      ) : (
        <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
          <Table stickyHeader containerClassName="max-h-[70vh]">
            <TableHeader>
              <TableRow>
                <TableHead className="w-10 text-right tabular-nums">#</TableHead>
                <TableHead>Student</TableHead>
                <TableHead className="hidden sm:table-cell">Batches</TableHead>
                <TableHead className="text-right hidden sm:table-cell">
                  Present
                </TableHead>
                <TableHead className="text-right">Attendance</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r, i) => (
                <TableRow key={r.student_id}>
                  <TableCell className="text-right tabular-nums text-muted-foreground text-xs">
                    {i + 1}
                  </TableCell>
                  <TableCell>
                    <Link
                      href={`/students/${r.student_id}`}
                      className="flex flex-col gap-0.5 hover:underline"
                    >
                      <span className="font-medium">{r.name}</span>
                      {r.enrollment_number && (
                        <span className="text-xs text-muted-foreground tabular-nums">
                          {r.enrollment_number}
                        </span>
                      )}
                    </Link>
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {r.batches.map((b) => (
                        <Badge key={b} variant="secondary" className="text-[10px]">
                          {b}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-sm text-muted-foreground hidden sm:table-cell">
                    {r.present}/{r.working_days}
                  </TableCell>
                  <TableCell
                    className={`text-right font-semibold tabular-nums ${pctTone(r.attendance_pct)}`}
                  >
                    {r.attendance_pct.toFixed(0)}%
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
