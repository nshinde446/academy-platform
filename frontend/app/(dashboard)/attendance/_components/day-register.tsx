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
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useRowSelection } from "@/hooks/use-row-selection";
import {
  useClassroomRegister,
  useDownloadAttendanceReport,
  useManualMarkDay,
  useSendDayNotification,
} from "../_hooks/use-attendance";
import type { ClassroomRegisterRow } from "../_schemas/attendance";

const SELECT_CLASS =
  "h-9 rounded-lg border border-input bg-background px-3 text-sm";

type StatusFilter = "all" | "present" | "absent";

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
  // Manual marking is a super-admin-only capability (matches the backend
  // require_roles(["super_admin"]) on /attendance/daily/mark).
  isSuperAdmin: boolean;
}

// Classroom day register (Reference B export): the whole batch roster for one
// day collapsed to P/A, derived from biometric day-attendance — independent of
// any single lecture.
export function DayRegister({ branchId, batches, isSuperAdmin }: DayRegisterProps) {
  const [batchId, setBatchId] = useState("");
  const [day, setDay] = useState(todayLocalISO());
  // Report range — defaults to the current month.
  const [from, setFrom] = useState(monthStartISO());
  const [to, setTo] = useState(todayLocalISO());
  const [studentId, setStudentId] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [markTarget, setMarkTarget] = useState<ClassroomRegisterRow | null>(null);

  const toast = useToast();
  const selection = useRowSelection();

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
  // The Present/Absent filter then sorts absentees apart from present students.
  const visibleRows = useMemo(() => {
    let list =
      studentId && rows.some((r) => r.student_id === studentId)
        ? rows.filter((r) => r.student_id === studentId)
        : rows;
    if (statusFilter === "present") list = list.filter((r) => r.mark === "P");
    else if (statusFilter === "absent") list = list.filter((r) => r.mark === "A");
    return list;
  }, [rows, studentId, statusFilter]);

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
  function pullDay(fmt: "xlsx" | "pdf") {
    download.mutate({ scope: "day", id: batchId, day, start: from, end: to, fmt });
  }

  const manualMark = useManualMarkDay(branchId, batchId || undefined, day || undefined);
  async function confirmManualMark() {
    if (!markTarget) return;
    try {
      await manualMark.mutateAsync({ student_id: markTarget.student_id, status: "PRESENT" });
      toast.success("Marked present", `${markTarget.name} marked present manually.`);
    } catch {
      toast.error("Couldn't mark", "Please try again.");
    }
  }

  const notify = useSendDayNotification(branchId);
  async function sendNotifications() {
    if (selection.count === 0 || !batchId) return;
    try {
      const res = await notify.mutateAsync({
        batch_id: batchId,
        day,
        student_ids: selection.selected,
      });
      selection.clear();
      toast.success(
        "Notifications queued",
        `${res.queued} parent message${res.queued === 1 ? "" : "s"} queued.`,
      );
    } catch {
      toast.error("Couldn't queue", "Please try again.");
    }
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

  const visibleIds = useMemo(
    () => visibleRows.map((r) => r.student_id),
    [visibleRows],
  );
  const allVisibleSelected =
    visibleIds.length > 0 && visibleIds.every((id) => selection.isSelected(id));

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
            selection.clear();
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
          onChange={(e) => {
            setDay(e.target.value);
            selection.clear();
          }}
          className={SELECT_CLASS}
          aria-label="Select day"
        />
        {/* Present / Absent filter — sort absentees apart from present. */}
        {batchId && rows.length > 0 && (
          <div
            role="radiogroup"
            aria-label="Filter by status"
            className="inline-flex rounded-lg border border-input p-0.5"
          >
            {(
              [
                ["all", "All"],
                ["present", "Present"],
                ["absent", "Absent"],
              ] as [StatusFilter, string][]
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={statusFilter === value}
                onClick={() => setStatusFilter(value)}
                className={`rounded-md px-3 py-1 text-[13px] font-medium transition-colors ${
                  statusFilter === value
                    ? "bg-primary text-primary-foreground"
                    : "text-foreground hover:bg-muted"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        )}
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
                complete even after batch or profile changes. The Day report is a
                single-day snapshot for the selected batch and day.
              </p>
              <div className="flex flex-wrap gap-4">
                <DownloadGroup
                  label={`Day report (${day})`}
                  disabled={!batchId || download.isPending}
                  onExcel={() => pullDay("xlsx")}
                  onPdf={() => pullDay("pdf")}
                />
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

      {/* Send-notification selection bar */}
      {selection.count > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2">
          <span className="text-sm font-medium">
            {selection.count} student{selection.count === 1 ? "" : "s"} selected
          </span>
          <Button
            size="sm"
            onClick={sendNotifications}
            disabled={notify.isPending}
          >
            Send WhatsApp notification
          </Button>
          <Button variant="ghost" size="sm" onClick={selection.clear} disabled={notify.isPending}>
            Clear
          </Button>
        </div>
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
                <TableHead className="w-10">
                  <input
                    type="checkbox"
                    aria-label="Select all shown"
                    checked={allVisibleSelected}
                    onChange={() => selection.toggleAll(visibleIds)}
                    className="size-4 align-middle"
                  />
                </TableHead>
                <TableHead className="w-10 text-right tabular-nums">#</TableHead>
                <TableHead>PRN</TableHead>
                <TableHead>Student</TableHead>
                <TableHead className="hidden sm:table-cell">In</TableHead>
                <TableHead className="hidden sm:table-cell">Out</TableHead>
                <TableHead className="text-right">Status</TableHead>
                {isSuperAdmin && <TableHead className="text-right">Action</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibleRows.map((r, i) => (
                <RegisterRow
                  key={r.student_id}
                  row={r}
                  index={i}
                  timeOf={timeOf}
                  selected={selection.isSelected(r.student_id)}
                  onToggle={() => selection.toggle(r.student_id)}
                  isSuperAdmin={isSuperAdmin}
                  onMarkPresent={() => setMarkTarget(r)}
                />
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <ConfirmDialog
        open={!!markTarget}
        onOpenChange={(o) => !o && setMarkTarget(null)}
        title="Mark present manually?"
        description={
          markTarget
            ? `Mark ${markTarget.name} present for ${day}? This is recorded as a manual mark (tagged "Manually Marked") and won't be overwritten by a later biometric sync.`
            : ""
        }
        confirmLabel="Mark present"
        onConfirm={confirmManualMark}
      />
    </div>
  );
}

function RegisterRow({
  row,
  index,
  timeOf,
  selected,
  onToggle,
  isSuperAdmin,
  onMarkPresent,
}: {
  row: ClassroomRegisterRow;
  index: number;
  timeOf: (iso: string | null) => string;
  selected: boolean;
  onToggle: () => void;
  isSuperAdmin: boolean;
  onMarkPresent: () => void;
}) {
  const present = row.mark === "P";
  const isManual = row.source === "MANUAL";
  return (
    <TableRow>
      <TableCell>
        <input
          type="checkbox"
          aria-label={`Select ${row.name}`}
          checked={selected}
          onChange={onToggle}
          className="size-4 align-middle"
        />
      </TableCell>
      <TableCell className="text-right tabular-nums text-muted-foreground text-xs">
        {index + 1}
      </TableCell>
      <TableCell className="tabular-nums text-sm text-muted-foreground">
        {row.enrollment_number || "—"}
      </TableCell>
      <TableCell className="font-medium">{row.name}</TableCell>
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
        <div className="flex items-center justify-end gap-1.5">
          {isManual && (
            <span
              className="rounded border border-primary/40 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary"
              title="Marked by hand, not a biometric punch"
            >
              Manually Marked
            </span>
          )}
          {present ? (
            <Badge variant={row.day_status === "LATE" ? "warning" : "success"}>
              {row.day_status === "LATE" ? "Late" : "Present"}
            </Badge>
          ) : (
            <Badge variant="destructive">Absent</Badge>
          )}
        </div>
      </TableCell>
      {isSuperAdmin && (
        <TableCell className="text-right">
          {!present && (
            <Button variant="outline" size="xs" onClick={onMarkPresent}>
              Mark present
            </Button>
          )}
        </TableCell>
      )}
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
