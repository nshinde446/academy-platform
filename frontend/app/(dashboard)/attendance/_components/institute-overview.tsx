"use client";

import { useMemo, useState } from "react";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Card, CardContent } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/info-hint";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useBranchSummary } from "../_hooks/use-attendance";
import type { BranchSummaryRow } from "../_schemas/attendance";

const CONTROL_CLASS =
  "h-9 rounded-lg border border-input bg-background px-3 text-sm";

function localISO(d: Date): string {
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
}

function todayLocalISO(): string {
  return localISO(new Date());
}

function pctTone(pct: number): string {
  if (pct >= 75) return "text-emerald-600 dark:text-emerald-400";
  if (pct < 60) return "text-destructive";
  return "text-amber-600 dark:text-amber-400";
}

function pctBg(pct: number): string {
  if (pct >= 75) return "bg-emerald-500";
  if (pct < 60) return "bg-destructive";
  return "bg-amber-500";
}

interface InstituteOverviewProps {
  branchId: string | undefined;
}

// Institute "today at a glance": one snapshot day across every batch. Batches
// with a scheduled session that day (working_days > 0) roll up into the
// headline present %, and each batch is listed worst-first so the batches
// needing attention surface immediately.
export function InstituteOverview({ branchId }: InstituteOverviewProps) {
  const [day, setDay] = useState(todayLocalISO());

  const query = useBranchSummary(branchId, day, day);
  const allRows = useMemo<BranchSummaryRow[]>(
    () => query.data ?? [],
    [query.data],
  );

  // Only batches actually in session that day count toward the headline.
  const inSession = useMemo(
    () =>
      [...allRows]
        .filter((r) => r.working_days > 0)
        .sort((a, b) => a.avg_pct - b.avg_pct),
    [allRows],
  );
  const notInSession = allRows.length - inSession.length;

  const totals = useMemo(() => {
    let present = 0;
    let slots = 0;
    for (const r of inSession) {
      present += r.present;
      slots += r.total_slots;
    }
    const pct = slots > 0 ? (present / slots) * 100 : 0;
    return { present, slots, absent: slots - present, pct, batches: inSession.length };
  }, [inSession]);

  const isToday = day === todayLocalISO();

  return (
    <div className="flex flex-col gap-4">
      {/* Day picker */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="date"
          value={day}
          max={todayLocalISO()}
          onChange={(e) => setDay(e.target.value)}
          className={CONTROL_CLASS}
          aria-label="Overview day"
        />
        <span className="text-sm text-muted-foreground">
          {isToday ? "Today" : "As of this day"}
        </span>
        <InfoHint
          text={
            <>
              A whole-institute snapshot for one day. Present % rolls up every
              batch with a scheduled session that day; batches are listed
              worst-first so the ones needing attention surface. Auto-refreshes
              while open.
            </>
          }
        />
      </div>

      {/* Headline KPIs */}
      <Card size="sm">
        <CardContent>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Kpi
              label="Present"
              value={
                totals.slots > 0 ? `${totals.pct.toFixed(0)}%` : "—"
              }
              tone={
                totals.slots === 0
                  ? "default"
                  : totals.pct < 60
                    ? "destructive"
                    : "success"
              }
            />
            <Kpi
              label="Present / total"
              value={`${totals.present}/${totals.slots}`}
            />
            <Kpi label="Absent" value={String(totals.absent)} />
            <Kpi label="Batches in session" value={String(totals.batches)} />
          </div>
        </CardContent>
      </Card>

      {/* Per-batch breakdown */}
      {!branchId ? (
        <p className="text-muted-foreground text-sm">No branch selected.</p>
      ) : query.isLoading ? (
        <TableSkeleton rows={6} />
      ) : query.isError ? (
        <p className="text-destructive text-sm">Failed to load the overview.</p>
      ) : inSession.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No batch has a scheduled session on this day.
        </p>
      ) : (
        <>
          <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
            <Table stickyHeader containerClassName="max-h-[70vh]">
              <TableHeader>
                <TableRow>
                  <TableHead>Batch</TableHead>
                  <TableHead className="text-right">Students</TableHead>
                  <TableHead className="text-right hidden sm:table-cell">
                    Present
                  </TableHead>
                  <TableHead className="text-right hidden sm:table-cell">
                    Absent
                  </TableHead>
                  <TableHead className="text-right">Attendance</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {inSession.map((r) => {
                  const absent = r.total_slots - r.present;
                  return (
                    <TableRow key={r.batch_id}>
                      <TableCell>
                        <div className="flex items-center gap-2.5">
                          <span
                            aria-hidden
                            className={`h-2 w-2 shrink-0 rounded-full ${pctBg(r.avg_pct)}`}
                          />
                          <div className="flex flex-col gap-0.5">
                            <span className="font-medium">{r.batch_name}</span>
                            {r.batch_code && (
                              <span className="text-xs text-muted-foreground tabular-nums">
                                {r.batch_code}
                              </span>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-sm">
                        {r.student_count}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-sm hidden sm:table-cell">
                        {r.present}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-sm hidden sm:table-cell">
                        {absent}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <span className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-muted sm:block">
                            <span
                              className={`block h-full rounded-full ${pctBg(r.avg_pct)}`}
                              style={{ width: `${Math.max(r.avg_pct, 3)}%` }}
                            />
                          </span>
                          <span
                            className={`font-semibold tabular-nums ${pctTone(r.avg_pct)}`}
                          >
                            {r.avg_pct.toFixed(0)}%
                          </span>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
          {notInSession > 0 && (
            <p className="text-xs text-muted-foreground">
              {notInSession} batch{notInSession === 1 ? "" : "es"} not in session
              this day.
            </p>
          )}
        </>
      )}
    </div>
  );
}

function Kpi({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "success" | "destructive";
}) {
  const cls =
    tone === "destructive"
      ? "text-destructive"
      : tone === "success"
        ? "text-emerald-600 dark:text-emerald-400"
        : "text-foreground";
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`text-xl font-semibold tabular-nums ${cls}`}>{value}</span>
    </div>
  );
}
