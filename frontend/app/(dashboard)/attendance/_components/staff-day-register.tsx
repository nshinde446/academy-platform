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
import { Card, CardContent } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useDepartments } from "../../staff/_hooks/use-staff";
import { useStaffDayRegister } from "../_hooks/use-staff-attendance";
import type { StaffDayRegisterRow } from "../_schemas/staff-attendance";

const SELECT_CLASS =
  "h-9 rounded-lg border border-input bg-background px-3 text-sm";

const PRESENT = new Set(["PRESENT", "LATE", "HALF_DAY"]);

function localISO(d: Date): string {
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
}

function fmtDuration(min: number): string {
  if (!min) return "—";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h ? `${h}h ${m}m` : `${m}m`;
}

function StatusBadge({ status }: { status: string }) {
  if (status === "PRESENT")
    return <Badge variant="success">Present</Badge>;
  if (status === "LATE") return <Badge variant="warning">Late</Badge>;
  if (status === "HALF_DAY")
    return <Badge variant="warning">Half day</Badge>;
  if (status === "WO")
    return <Badge variant="secondary">Weekly off</Badge>;
  if (status === "HOLIDAY")
    return <Badge variant="secondary">Holiday</Badge>;
  return <Badge variant="destructive">Absent</Badge>;
}

// Staff day register — one day's staff in/out roster (the staff twin of the
// student Day Register), so staff attendance is tracked daily. Read-only:
// staff punch on the same BioMax fleet; rows roll up automatically.
export function StaffDayRegister({ branchId }: { branchId: string | undefined }) {
  const [day, setDay] = useState(localISO(new Date()));
  const [departmentId, setDepartmentId] = useState("");

  const departmentsQuery = useDepartments(branchId);
  const departments = useMemo(
    () => departmentsQuery.data ?? [],
    [departmentsQuery.data],
  );

  const registerQuery = useStaffDayRegister(
    branchId,
    day || undefined,
    departmentId || undefined,
  );
  const rows: StaffDayRegisterRow[] = useMemo(
    () => registerQuery.data ?? [],
    [registerQuery.data],
  );

  const counts = useMemo(() => {
    let present = 0;
    let absent = 0;
    let missingOut = 0;
    let considered = 0;
    for (const r of rows) {
      if (r.status === "WO" || r.status === "HOLIDAY") continue;
      considered += 1;
      if (PRESENT.has(r.status)) present += 1;
      else absent += 1;
      if (r.missed_signoff) missingOut += 1;
    }
    const pct = considered > 0 ? (present / considered) * 100 : 0;
    return { present, absent, missingOut, considered, pct };
  }, [rows]);

  return (
    <div className="flex flex-col gap-4">
      {/* Pickers */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          type="date"
          value={day}
          onChange={(e) => setDay(e.target.value)}
          className={SELECT_CLASS}
          aria-label="Select day"
        />
        <select
          value={departmentId}
          onChange={(e) => setDepartmentId(e.target.value)}
          className={SELECT_CLASS}
          aria-label="Filter by department"
        >
          <option value="">All departments</option>
          {departments.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </div>

      {/* KPI strip */}
      {rows.length > 0 && (
        <Card size="sm">
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Kpi
                label="Present"
                value={`${counts.pct.toFixed(0)}%`}
                tone={counts.pct < 60 ? "destructive" : "success"}
              />
              <Kpi
                label="Present / staff"
                value={`${counts.present}/${counts.considered}`}
              />
              <Kpi label="Absent" value={String(counts.absent)} />
              <Kpi label="Missed punch-out" value={String(counts.missingOut)} />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Register */}
      {!branchId ? (
        <p className="text-muted-foreground text-sm">No branch selected.</p>
      ) : registerQuery.isLoading ? (
        <TableSkeleton rows={6} />
      ) : registerQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to load the staff register.
        </p>
      ) : rows.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No staff found for this branch{departmentId ? " / department" : ""}.
        </p>
      ) : (
        <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
          <Table stickyHeader containerClassName="max-h-[70vh]">
            <TableHeader>
              <TableRow>
                <TableHead className="w-10 text-right tabular-nums">#</TableHead>
                <TableHead>Code</TableHead>
                <TableHead>Staff</TableHead>
                <TableHead className="hidden md:table-cell">Department</TableHead>
                <TableHead className="hidden sm:table-cell">In</TableHead>
                <TableHead className="hidden sm:table-cell">Out</TableHead>
                <TableHead className="hidden lg:table-cell text-right">
                  Work
                </TableHead>
                <TableHead className="hidden lg:table-cell text-right">
                  OT
                </TableHead>
                <TableHead className="text-right">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r, i) => (
                <TableRow key={r.staff_id}>
                  <TableCell className="text-right tabular-nums text-muted-foreground text-xs">
                    {i + 1}
                  </TableCell>
                  <TableCell className="font-mono text-sm">{r.emp_code}</TableCell>
                  <TableCell className="font-medium">{r.name}</TableCell>
                  <TableCell className="hidden md:table-cell text-muted-foreground">
                    {r.department}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell tabular-nums text-sm">
                    {r.in_time ?? "—"}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell tabular-nums text-sm">
                    {r.out_time ?? "—"}
                    {r.missed_signoff && (
                      <span
                        className="ml-1 text-xs text-amber-600 dark:text-amber-500"
                        title="Punched in, never punched out"
                      >
                        ⚠
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-right tabular-nums text-sm text-muted-foreground">
                    {fmtDuration(r.work_minutes)}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-right tabular-nums text-sm text-muted-foreground">
                    {fmtDuration(r.ot_minutes)}
                  </TableCell>
                  <TableCell className="text-right">
                    <StatusBadge status={r.status} />
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
