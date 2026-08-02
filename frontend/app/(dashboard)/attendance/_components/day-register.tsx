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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  useClassroomRegister,
  useDownloadAttendanceReport,
} from "../_hooks/use-attendance";
import type { ClassroomRegisterRow } from "../_schemas/attendance";

const SELECT_CLASS =
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

function timeOf(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

interface DayRegisterProps {
  branchId: string | undefined;
  batches: { id: string; name: string }[];
}

// Classroom day register (Reference B export): the whole batch roster for one
// day collapsed to P/A, derived from biometric day-attendance — independent of
// any single lecture.
export function DayRegister({ branchId, batches }: DayRegisterProps) {
  const [batchId, setBatchId] = useState("");
  const [day, setDay] = useState(todayLocalISO());
  // Report range — defaults to the current month.
  const [from, setFrom] = useState(monthStartISO());
  const [to, setTo] = useState(todayLocalISO());
  const [studentId, setStudentId] = useState("");

  const registerQuery = useClassroomRegister(
    branchId,
    batchId || undefined,
    day || undefined,
  );
  const rows = useMemo(
    () => registerQuery.data ?? [],
    [registerQuery.data],
  );
  // The Student filter narrows the visible roster; empty selection = whole batch.
  // A stale selection (student not in the current batch) falls back to all rows.
  const visibleRows = useMemo(
    () =>
      studentId && rows.some((r) => r.student_id === studentId)
        ? rows.filter((r) => r.student_id === studentId)
        : rows,
    [rows, studentId],
  );

  const download = useDownloadAttendanceReport(branchId);
  function pull(
    scope: "student" | "batch" | "all-batches" | "daily-ledger",
    fmt: "xlsx" | "pdf",
  ) {
    download.mutate({
      scope,
      id: scope === "student" ? studentId : scope === "batch" ? batchId : undefined,
      start: from,
      end: to,
      fmt,
    });
  }

  const counts = useMemo(() => {
    let present = 0;
    let missingOut = 0;
    for (const r of rows) {
      if (r.mark === "P") present += 1;
      if (r.signoff === "MISSING") missingOut += 1;
    }
    const total = rows.length;
    const pct = total > 0 ? (present / total) * 100 : 0;
    return { present, absent: total - present, missingOut, total, pct };
  }, [rows]);

  return (
    <div className="flex flex-col gap-4">
      {/* Pickers */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <select
          value={batchId}
          onChange={(e) => {
            setBatchId(e.target.value);
            // A student from the previous batch shouldn't leak the filter over.
            setStudentId("");
          }}
          className={SELECT_CLASS}
          aria-label="Select batch"
        >
          <option value="">Select a batch…</option>
          {batches.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={day}
          onChange={(e) => setDay(e.target.value)}
          className={SELECT_CLASS}
          aria-label="Select day"
        />
      </div>

      {/* KPI strip */}
      {batchId && rows.length > 0 && (
        <Card size="sm">
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Kpi
                label="Present"
                value={`${counts.pct.toFixed(0)}%`}
                tone={counts.pct < 60 ? "destructive" : "success"}
              />
              <Kpi label="Present / total" value={`${counts.present}/${counts.total}`} />
              <Kpi label="Absent" value={String(counts.absent)} />
              <Kpi label="Missed punch-out" value={String(counts.missingOut)} />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Downloadable reports */}
      {branchId && (
        <Card size="sm">
          <CardContent>
            <div className="flex flex-col gap-3">
              <span className="text-sm font-medium">Download reports</span>
              <div className="flex flex-wrap items-end gap-3">
                <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                  From
                  <input
                    type="date"
                    value={from}
                    max={to}
                    onChange={(e) => setFrom(e.target.value)}
                    className={SELECT_CLASS}
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                  To
                  <input
                    type="date"
                    value={to}
                    min={from}
                    onChange={(e) => setTo(e.target.value)}
                    className={SELECT_CLASS}
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                  Student
                  <select
                    value={studentId}
                    onChange={(e) => setStudentId(e.target.value)}
                    className={`${SELECT_CLASS} min-w-44`}
                    disabled={rows.length === 0}
                  >
                    <option value="">All students</option>
                    {rows.map((r) => (
                      <option key={r.student_id} value={r.student_id}>
                        {r.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <p className="text-xs text-muted-foreground">
                {studentId
                  ? "Download covers the selected student for the date range."
                  : "No student selected — download covers the whole batch for the date range."}{" "}
                The daily ledger is the permanent per-student record — it stays
                complete even after batch or profile changes.
              </p>
              <div className="flex flex-wrap gap-4">
                <DownloadGroup
                  label={studentId ? "Selected student" : "This batch"}
                  disabled={!batchId || download.isPending}
                  onExcel={() => pull(studentId ? "student" : "batch", "xlsx")}
                  onPdf={() => pull(studentId ? "student" : "batch", "pdf")}
                />
                <DownloadGroup
                  label="All batches"
                  disabled={download.isPending}
                  onExcel={() => pull("all-batches", "xlsx")}
                  onPdf={() => pull("all-batches", "pdf")}
                />
                <DownloadGroup
                  label="Daily ledger (all students)"
                  disabled={download.isPending}
                  onExcel={() => pull("daily-ledger", "xlsx")}
                  onPdf={() => pull("daily-ledger", "pdf")}
                />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Register */}
      {!batchId ? (
        <p className="text-muted-foreground text-sm">
          Pick a batch and day to see the campus attendance register.
        </p>
      ) : registerQuery.isLoading ? (
        <TableSkeleton rows={6} />
      ) : registerQuery.isError ? (
        <p className="text-destructive text-sm">Failed to load the register.</p>
      ) : rows.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No students enrolled in this batch yet.
        </p>
      ) : (
        <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
          <Table stickyHeader containerClassName="max-h-[70vh]">
            <TableHeader>
              <TableRow>
                <TableHead className="w-10 text-right tabular-nums">#</TableHead>
                <TableHead>Student</TableHead>
                <TableHead className="hidden sm:table-cell">In</TableHead>
                <TableHead className="hidden sm:table-cell">Out</TableHead>
                <TableHead className="text-right">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibleRows.map((r, i) => (
                <RegisterRow key={r.student_id} row={r} index={i} timeOf={timeOf} />
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function RegisterRow({
  row,
  index,
  timeOf,
}: {
  row: ClassroomRegisterRow;
  index: number;
  timeOf: (iso: string | null) => string;
}) {
  const present = row.mark === "P";
  return (
    <TableRow>
      <TableCell className="text-right tabular-nums text-muted-foreground text-xs">
        {index + 1}
      </TableCell>
      <TableCell>
        <div className="flex flex-col gap-0.5">
          <span className="font-medium">{row.name}</span>
          {row.enrollment_number && (
            <span className="text-xs text-muted-foreground tabular-nums">
              {row.enrollment_number}
            </span>
          )}
        </div>
      </TableCell>
      <TableCell className="hidden sm:table-cell tabular-nums text-sm">
        {timeOf(row.first_in)}
      </TableCell>
      <TableCell className="hidden sm:table-cell tabular-nums text-sm">
        {timeOf(row.last_out)}
        {row.signoff === "MISSING" && (
          <span
            className="ml-1 text-xs text-amber-600 dark:text-amber-500"
            title="Punched in, never punched out"
          >
            ⚠
          </span>
        )}
      </TableCell>
      <TableCell className="text-right">
        {present ? (
          <Badge variant={row.day_status === "LATE" ? "warning" : "success"}>
            {row.day_status === "LATE" ? "Late" : "Present"}
          </Badge>
        ) : (
          <Badge variant="destructive">Absent</Badge>
        )}
      </TableCell>
    </TableRow>
  );
}

function DownloadGroup({
  label,
  disabled,
  onExcel,
  onPdf,
}: {
  label: string;
  disabled?: boolean;
  onExcel: () => void;
  onPdf: () => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <div className="flex gap-1.5">
        <Button variant="outline" size="sm" disabled={disabled} onClick={onExcel}>
          Excel
        </Button>
        <Button variant="outline" size="sm" disabled={disabled} onClick={onPdf}>
          PDF
        </Button>
      </div>
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
