"use client";

import { useState } from "react";
import Link from "next/link";
import { useUserStore } from "@/store/user-store";
import apiClient from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/layout/page-header";
import { useDepartments } from "../_hooks/use-staff";

const REPORT_KINDS: { value: string; label: string }[] = [
  { value: "performance", label: "Performance (grid)" },
  { value: "present", label: "Present" },
  { value: "absent", label: "Absent" },
  { value: "late_in", label: "Late IN" },
  { value: "early_out", label: "Early OUT" },
  { value: "early_in", label: "Early IN" },
  { value: "over_time", label: "Over Time" },
  { value: "half_day", label: "Half Day" },
  { value: "mis_punch", label: "Mis Punch" },
  { value: "in_out", label: "In / Out" },
  { value: "short_performance", label: "Short Performance" },
  { value: "gps_approved", label: "GPS Approved (N/A)" },
  { value: "gps_rejected", label: "GPS Rejected (N/A)" },
  { value: "gps_pending", label: "GPS Pending (N/A)" },
];

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

async function downloadFile(path: string, params: URLSearchParams) {
  const res = await apiClient.get(`${path}?${params.toString()}`, {
    responseType: "blob",
  });
  const disposition = res.headers["content-disposition"] as string | undefined;
  const match = disposition?.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? "report";
  const url = window.URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export default function StaffReportsPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;
  const departmentsQuery = useDepartments(branchId);
  const departments = departmentsQuery.data ?? [];

  const [kind, setKind] = useState("performance");
  const [frequency, setFrequency] = useState("monthly");
  const [deptId, setDeptId] = useState("");
  const [start, setStart] = useState(isoToday());
  const [end, setEnd] = useState(isoToday());
  const [fmt, setFmt] = useState("pdf");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleDownload() {
    if (!branchId) return;
    setBusy(true);
    setError("");
    try {
      const params = new URLSearchParams({
        branch_id: branchId,
        kind,
        frequency,
        start,
        end,
        fmt,
      });
      if (deptId) params.append("department_ids", deptId);
      await downloadFile("/api/v1/staff/reports", params);
    } catch {
      setError("Download failed. Check the date range and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Staff Reports"
        description="Daily / weekly / monthly attendance — department-wise or all staff, as PDF or Excel."
        actions={
          <Button variant="secondary" size="sm" render={<Link href="/staff" />}>
            Back to roster
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-4 rounded-lg border p-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="r_kind">Report</Label>
          <select
            id="r_kind"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            {REPORT_KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="r_freq">Frequency</Label>
          <select
            id="r_freq"
            value={frequency}
            onChange={(e) => setFrequency(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="r_dept">Department</Label>
          <select
            id="r_dept"
            value={deptId}
            onChange={(e) => setDeptId(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="">All departments</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="r_start">From</Label>
          <Input
            id="r_start"
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="r_end">To</Label>
          <Input
            id="r_end"
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="r_fmt">Format</Label>
          <select
            id="r_fmt"
            value={fmt}
            onChange={(e) => setFmt(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="pdf">PDF</option>
            <option value="xlsx">Excel</option>
          </select>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      <div>
        <Button onClick={handleDownload} disabled={busy}>
          {busy ? "Generating…" : "Download report"}
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">
        GPS reports are not applicable — the biometric fleet has no GPS source;
        selecting one produces a file with an explanatory note. For the
        teacher-lecture activity report, see{" "}
        <Link href="/teachers/faculty-activity" className="underline">
          Faculty Activity
        </Link>
        .
      </p>
    </div>
  );
}
