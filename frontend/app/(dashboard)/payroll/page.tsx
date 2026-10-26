"use client";

import { useState } from "react";
import Link from "next/link";
import { useBranchId } from "@/store/user-store";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  downloadPayroll,
  usePayrollDepartments,
  usePayrollReport,
  type ReportRow,
} from "@/hooks/use-payroll";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function num(v: number): string {
  return v === Math.trunc(v) ? String(v) : v.toFixed(1);
}

function signed(v: number): string {
  return `${v > 0 ? "+" : ""}${num(v)}`;
}

const LIFECYCLE_TONE: Record<string, "default" | "secondary" | "outline"> = {
  OPEN: "secondary",
  CLOSED: "default",
  LOCKED: "outline",
  NOT_SET: "outline",
};

export default function PayrollReportPage() {
  const { branchId } = useBranchId();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [departmentId, setDepartmentId] = useState("");
  const [busy, setBusy] = useState(false);

  const depts = usePayrollDepartments(branchId).data ?? [];
  const report = usePayrollReport(branchId, year, month, departmentId || undefined);

  async function exportAs(fmt: "pdf" | "xlsx") {
    if (!branchId) return;
    setBusy(true);
    try {
      await downloadPayroll("/api/v1/payroll/report/export", {
        branch_id: branchId,
        year: String(year),
        month: String(month),
        fmt,
        ...(departmentId ? { department_id: departmentId } : {}),
      });
    } finally {
      setBusy(false);
    }
  }

  const data = report.data;
  const years = Array.from({ length: 6 }, (_, i) => now.getFullYear() - i);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Payroll Report"
        description="Per-staff days for the month: required, present, carry-forward in/out, uncovered shortfall and late fine. A live preview while the month is open; the final figures once it is closed."
        actions={
          <>
            <Button variant="outline" render={<Link href="/payroll/setup" />}>
              Month Setup
            </Button>
            <Button variant="outline" disabled={busy || !data?.rows.length} onClick={() => exportAs("xlsx")}>
              Excel
            </Button>
            <Button variant="outline" disabled={busy || !data?.rows.length} onClick={() => exportAs("pdf")}>
              PDF
            </Button>
          </>
        }
      >
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
          >
            {MONTHS.map((m, i) => (
              <option key={m} value={i + 1}>{m}</option>
            ))}
          </select>
          <select
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
          >
            {years.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <select
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
          >
            <option value="">All departments</option>
            {depts.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
          {data && (
            <Badge variant={LIFECYCLE_TONE[data.lifecycle] ?? "outline"}>
              {data.lifecycle === "OPEN" ? "Preview" : data.lifecycle}
            </Badge>
          )}
        </div>
      </PageHeader>

      {report.isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      ) : report.isError ? (
        <ErrorState onRetry={() => report.refetch()} />
      ) : !data || data.rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {data?.lifecycle === "NOT_SET"
            ? "This month has not been set up yet. Open Month Setup to set the required days."
            : "No staff for this selection."}
        </p>
      ) : (
        <Table containerClassName="rounded-md border">
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Dept</TableHead>
              <TableHead className="text-right">Req.</TableHead>
              <TableHead className="text-right">Present</TableHead>
              <TableHead className="text-right">Paid L/H</TableHead>
              <TableHead className="text-right">Net</TableHead>
              <TableHead className="text-right">CF in</TableHead>
              <TableHead className="text-right">CF out</TableHead>
              <TableHead className="text-right">Uncovered</TableHead>
              <TableHead className="text-right">Late fine</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.rows.map((r: ReportRow) => (
              <TableRow key={r.staff_id}>
                <TableCell className="font-mono text-xs">{r.emp_code}</TableCell>
                <TableCell>
                  <Link
                    href={`/payroll/ledger/${r.staff_id}`}
                    className="text-foreground underline-offset-2 hover:underline"
                  >
                    {r.name}
                  </Link>
                </TableCell>
                <TableCell className="text-muted-foreground">{r.department}</TableCell>
                <TableCell className="text-right">{num(r.required_days)}</TableCell>
                <TableCell className="text-right">
                  {num(r.present_days)}
                  {r.half_days > 0 && (
                    <span className="ml-1 text-xs text-muted-foreground">({r.half_days}½)</span>
                  )}
                </TableCell>
                <TableCell className="text-right">{num(r.paid_leave_days)}</TableCell>
                <TableCell className="text-right">{signed(r.net_days)}</TableCell>
                <TableCell className="text-right">{num(r.balance_in)}</TableCell>
                <TableCell className="text-right">{num(r.balance_out)}</TableCell>
                <TableCell className="text-right">
                  {r.uncovered_days > 0 ? (
                    <span className="font-medium text-destructive">{num(r.uncovered_days)}</span>
                  ) : (
                    num(r.uncovered_days)
                  )}
                  {r.deferred_days > 0 && (
                    <span className="ml-1 text-xs text-muted-foreground">(+{num(r.deferred_days)} def.)</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {r.late_fine_total > 0 ? `₹${num(r.late_fine_total)}` : "—"}
                </TableCell>
              </TableRow>
            ))}
            <TableRow className="border-t-2 font-medium">
              <TableCell colSpan={4}>Totals · {data.totals.staff_count} staff</TableCell>
              <TableCell className="text-right">{num(data.totals.present_days)}</TableCell>
              <TableCell colSpan={4} />
              <TableCell className="text-right">{num(data.totals.uncovered_days)}</TableCell>
              <TableCell className="text-right">₹{num(data.totals.late_fine_total)}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      )}
    </div>
  );
}
