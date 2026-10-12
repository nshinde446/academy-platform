"use client";

import { useState } from "react";
import Link from "next/link";
import { useBranchId } from "@/store/user-store";
import apiClient from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/layout/page-header";
import { useStaff } from "../_hooks/use-staff";

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

async function downloadFile(path: string, params: URLSearchParams) {
  const res = await apiClient.get(`${path}?${params.toString()}`, { responseType: "blob" });
  const disposition = res.headers["content-disposition"] as string | undefined;
  const filename = disposition?.match(/filename="?([^"]+)"?/)?.[1] ?? "late-fine";
  const url = window.URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export default function LateFinePage() {
  const { branchId } = useBranchId();
  const staffQuery = useStaff(branchId);
  const staff = staffQuery.data ?? [];

  const [staffId, setStaffId] = useState("");
  const [start, setStart] = useState(isoToday());
  const [end, setEnd] = useState(isoToday());
  const [fmt, setFmt] = useState("pdf");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function download() {
    setError("");
    if (!branchId || !staffId) return setError("Pick a staff member.");
    if (start > end) return setError("From date must not be after To date.");
    setBusy(true);
    try {
      await downloadFile(
        "/api/v1/staff/late-fine-report",
        new URLSearchParams({ branch_id: branchId, staff_id: staffId, start, end, fmt }),
      );
    } catch {
      setError("Download failed — there may be no attendance data for this selection.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Staff Late Fine Report"
        description="Per-staff lateness vs the First Lecture Start Time, with per-day fines — for a single day or a date range."
        actions={
          <Button variant="secondary" size="sm" render={<Link href="/staff" />}>
            Back to staff
          </Button>
        }
      />

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="rounded-lg border p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label htmlFor="lf_staff">Staff</Label>
            <select
              id="lf_staff"
              value={staffId}
              onChange={(e) => setStaffId(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">Select staff…</option>
              {staff.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.emp_code} · {s.first_name} {s.last_name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lf_from">From</Label>
            <Input id="lf_from" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lf_to">To</Label>
            <Input id="lf_to" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lf_fmt">Format</Label>
            <select
              id="lf_fmt"
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
            Single day: set From = To. Fines: 1–5 min ₹200 · 6–10 ₹500 · 11+ ₹1000.
          </span>
        </div>
      </div>
    </div>
  );
}
