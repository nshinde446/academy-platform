"use client";

import { useState } from "react";
import Link from "next/link";
import { useBranchId } from "@/store/user-store";
import apiClient from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/layout/page-header";
import { useDepartments } from "../_hooks/use-staff";

const MAX_DAYS = 62;

/** First and last day of the current month, as ISO dates. */
function currentMonthRange(): { start: string; end: string } {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  const last = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
      d.getDate(),
    ).padStart(2, "0")}`;
  return { start: iso(first), end: iso(last) };
}

function daysBetween(start: string, end: string): number {
  return Math.round((Date.parse(end) - Date.parse(start)) / 86_400_000) + 1;
}

async function downloadFile(path: string, params: URLSearchParams) {
  const res = await apiClient.get(`${path}?${params.toString()}`, { responseType: "blob" });
  const disposition = res.headers["content-disposition"] as string | undefined;
  const filename = disposition?.match(/filename="?([^"]+)"?/)?.[1] ?? "date-wise-attendance";
  const url = window.URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export default function DateWiseAttendancePage() {
  const { branchId } = useBranchId();
  const departmentsQuery = useDepartments(branchId);
  const departments = departmentsQuery.data ?? [];

  const initial = currentMonthRange();
  const [deptId, setDeptId] = useState(""); // "" = All Groups
  const [start, setStart] = useState(initial.start);
  const [end, setEnd] = useState(initial.end);
  const [fmt, setFmt] = useState("pdf");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function download() {
    setError("");
    if (!branchId) return;
    if (start > end) return setError("From date must not be after To date.");
    const span = daysBetween(start, end);
    if (span > MAX_DAYS)
      return setError(
        `Date range is ${span} days; the maximum for this report is ${MAX_DAYS} days. Narrow the range.`,
      );
    setBusy(true);
    try {
      const params = new URLSearchParams({ branch_id: branchId, start, end, fmt });
      if (deptId) params.append("department_ids", deptId);
      await downloadFile("/api/v1/staff/date-wise-report", params);
    } catch {
      setError("Download failed — there may be no attendance data for this selection.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Date Wise Attendance"
        description="Staff monthly grid — one row per staff, a coded cell per day (P/A/L/HD/WO/HL) with totals — as landscape PDF or Excel."
        actions={
          <Button variant="secondary" size="sm" render={<Link href="/staff" />}>
            Back to staff
          </Button>
        }
      />

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="rounded-lg border p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label htmlFor="dw_group">Group / Department</Label>
            <select
              id="dw_group"
              value={deptId}
              onChange={(e) => setDeptId(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">All Groups</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dw_from">From</Label>
            <Input id="dw_from" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dw_to">To</Label>
            <Input id="dw_to" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dw_fmt">Format</Label>
            <select
              id="dw_fmt"
              value={fmt}
              onChange={(e) => setFmt(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="pdf">PDF</option>
              <option value="xlsx">Excel</option>
            </select>
          </div>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <Button onClick={download} disabled={busy}>
            {busy ? "Generating…" : "Download report"}
          </Button>
          <span className="text-xs text-muted-foreground">
            Default range is the current month. Legend: P Present · A Absent · L Late · HD Half Day · WO Weekly Off · HL Holiday.
          </span>
        </div>
      </div>
    </div>
  );
}
