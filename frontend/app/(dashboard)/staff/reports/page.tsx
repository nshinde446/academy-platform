"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useUserStore } from "@/store/user-store";
import apiClient from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/layout/page-header";
import { useDepartments, useStaff } from "../_hooks/use-staff";
import { ScopeMultiSelect, type ScopeOption } from "../_components/scope-multiselect";

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
  const staffQuery = useStaff(branchId);
  const staff = useMemo(() => staffQuery.data ?? [], [staffQuery.data]);

  const [kind, setKind] = useState("performance");
  const [frequency, setFrequency] = useState("monthly");
  const [deptIds, setDeptIds] = useState<Set<string>>(new Set());
  const [staffIds, setStaffIds] = useState<Set<string>>(new Set());
  const [start, setStart] = useState(isoToday());
  const [end, setEnd] = useState(isoToday());
  const [fmt, setFmt] = useState("pdf");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Specific staff win over a department filter, matching the API's precedence
  // (staff_ids narrows before department_ids). When staff are chosen the
  // department scope is moot, so we gray it out to keep the two honest.
  const staffChosen = staffIds.size > 0;

  const deptOptions: ScopeOption[] = departments.map((d) => ({
    id: d.id,
    label: d.name,
  }));

  // Employee picker is scoped to the chosen departments so it stays short; the
  // full roster shows when no department is selected.
  const staffOptions: ScopeOption[] = useMemo(() => {
    const rows = deptIds.size
      ? staff.filter((s) => deptIds.has(s.department_id))
      : staff;
    return rows.map((s) => ({
      id: s.id,
      label: `${s.first_name} ${s.last_name}`.trim(),
      sublabel: `${s.emp_code}${s.department_name ? ` · ${s.department_name}` : ""}`,
    }));
  }, [staff, deptIds]);

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
      if (staffChosen) {
        staffIds.forEach((id) => params.append("staff_ids", id));
      } else {
        deptIds.forEach((id) => params.append("department_ids", id));
      }
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
        description="Daily / weekly / monthly attendance — all staff, chosen departments, or specific people, as PDF or Excel."
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

        <ScopeMultiSelect
          label="Departments"
          allLabel="All departments"
          options={deptOptions}
          selected={deptIds}
          onChange={setDeptIds}
          disabled={staffChosen}
          disabledNote="Ignored while specific staff are selected — clear the staff picker to filter by department."
          emptyNote="No departments yet."
        />

        <ScopeMultiSelect
          label="Staff"
          allLabel="All staff in scope"
          options={staffOptions}
          selected={staffIds}
          onChange={setStaffIds}
          searchable
          emptyNote={
            staffQuery.isLoading ? "Loading roster…" : "No staff in this scope."
          }
        />

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
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex items-center gap-3">
        <Button onClick={handleDownload} disabled={busy}>
          {busy ? "Generating…" : "Download report"}
        </Button>
        {(deptIds.size > 0 || staffIds.size > 0) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setDeptIds(new Set());
              setStaffIds(new Set());
            }}
          >
            Reset scope
          </Button>
        )}
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
