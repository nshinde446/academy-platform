"use client";

import { useState } from "react";
import Link from "next/link";
import { useUserStore } from "@/store/user-store";
import apiClient from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/layout/page-header";
import { useTeachers } from "../_hooks/use-teachers";

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Start/end for a Daily / Weekly / Monthly preset, ending today. */
function rangeForPreset(preset: "daily" | "weekly" | "monthly"): {
  start: string;
  end: string;
} {
  const end = new Date();
  const start = new Date(end);
  if (preset === "weekly") start.setDate(end.getDate() - 6);
  else if (preset === "monthly") start.setDate(end.getDate() - 29);
  return { start: iso(start), end: iso(end) };
}

async function downloadFile(path: string, params: URLSearchParams) {
  const res = await apiClient.get(`${path}?${params.toString()}`, {
    responseType: "blob",
  });
  const disposition = res.headers["content-disposition"] as string | undefined;
  const filename =
    disposition?.match(/filename="?([^"]+)"?/)?.[1] ?? "faculty-activity";
  const url = window.URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export default function FacultyActivityPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;
  const teachersQuery = useTeachers(branchId);
  const teachers = teachersQuery.data ?? [];

  const [teacherId, setTeacherId] = useState("");
  const [day, setDay] = useState(isoToday());
  const [start, setStart] = useState(isoToday());
  const [end, setEnd] = useState(isoToday());
  const [preset, setPreset] = useState<"daily" | "weekly" | "monthly" | "custom">(
    "daily",
  );
  const [fmt, setFmt] = useState("pdf");

  function applyPreset(next: "daily" | "weekly" | "monthly" | "custom") {
    setPreset(next);
    if (next !== "custom") {
      const r = rangeForPreset(next);
      setStart(r.start);
      setEnd(r.end);
    }
  }
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function daily() {
    if (!branchId || !teacherId) {
      setError("Pick a teacher.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await downloadFile(
        "/api/v1/staff/faculty-activity",
        new URLSearchParams({ branch_id: branchId, teacher_id: teacherId, day, fmt })
      );
    } catch {
      setError("Download failed.");
    } finally {
      setBusy(false);
    }
  }

  async function summary() {
    if (!branchId) return;
    setBusy(true);
    setError("");
    try {
      await downloadFile(
        "/api/v1/staff/faculty-activity/summary",
        new URLSearchParams({ branch_id: branchId, start, end, fmt })
      );
    } catch {
      setError("Download failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Faculty Activity"
        description="Teacher biometric attendance joined with lectures delivered — delays, effective hours, and a cumulative summary."
        actions={
          <Button variant="secondary" size="sm" render={<Link href="/teachers" />}>
            Back to teachers
          </Button>
        }
      />

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="rounded-lg border p-4">
        <h2 className="mb-3 text-sm font-semibold">Daily Faculty Activity</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label htmlFor="fa_teacher">Teacher</Label>
            <select
              id="fa_teacher"
              value={teacherId}
              onChange={(e) => setTeacherId(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">Select teacher…</option>
              {teachers.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.first_name} {t.last_name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fa_day">Day</Label>
            <Input
              id="fa_day"
              type="date"
              value={day}
              onChange={(e) => setDay(e.target.value)}
            />
          </div>
          <div className="flex items-end">
            <Button onClick={daily} disabled={busy} className="w-full">
              {busy ? "…" : "Download"}
            </Button>
          </div>
        </div>
      </div>

      <div className="rounded-lg border p-4">
        <h2 className="mb-3 text-sm font-semibold">
          Cumulative Summary (all teachers)
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4 lg:grid-cols-5">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fa_preset">Range</Label>
            <select
              id="fa_preset"
              value={preset}
              onChange={(e) =>
                applyPreset(
                  e.target.value as "daily" | "weekly" | "monthly" | "custom",
                )
              }
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="daily">Daily (today)</option>
              <option value="weekly">Weekly (7 days)</option>
              <option value="monthly">Monthly (30 days)</option>
              <option value="custom">Custom…</option>
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fa_start">From</Label>
            <Input
              id="fa_start"
              type="date"
              value={start}
              onChange={(e) => {
                setStart(e.target.value);
                setPreset("custom");
              }}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fa_end">To</Label>
            <Input
              id="fa_end"
              type="date"
              value={end}
              onChange={(e) => {
                setEnd(e.target.value);
                setPreset("custom");
              }}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fa_fmt">Format</Label>
            <select
              id="fa_fmt"
              value={fmt}
              onChange={(e) => setFmt(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="pdf">PDF</option>
              <option value="xlsx">Excel</option>
            </select>
          </div>
          <div className="flex items-end">
            <Button onClick={summary} disabled={busy} className="w-full">
              {busy ? "…" : "Download"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
