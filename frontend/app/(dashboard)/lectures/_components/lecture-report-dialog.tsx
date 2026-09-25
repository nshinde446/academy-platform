"use client";

import { useState } from "react";
import apiClient from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

interface Option {
  id: string;
  label: string;
}

interface LectureReportDialogProps {
  branchId: string | undefined;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Seed the range from the page's current date filter (may be empty). */
  fromDate?: string;
  toDate?: string;
  teachers?: Option[];
  batches?: Option[];
}

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Downloads the flat per-lecture **Lecture Report** (server-rendered Excel/PDF)
 * for a date range — all columns incl. Date, Branch, Attendance Updated By and
 * Timestamp, time-only schedule/actual columns, and Duration as minutes or HH:MM.
 */
export function LectureReportDialog({
  branchId,
  open,
  onOpenChange,
  fromDate,
  toDate,
  teachers = [],
  batches = [],
}: LectureReportDialogProps) {
  const [start, setStart] = useState(fromDate || isoToday());
  const [end, setEnd] = useState(toDate || isoToday());
  const [durationStyle, setDurationStyle] = useState<"min" | "hhmm">("min");
  const [fmt, setFmt] = useState<"xlsx" | "pdf">("xlsx");
  const [teacherId, setTeacherId] = useState("");
  const [batchId, setBatchId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleDownload() {
    if (!branchId) return;
    if (!start || !end) {
      setError("Pick a from and to date.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const params = new URLSearchParams({
        branch_id: branchId,
        start,
        end,
        duration_style: durationStyle,
        fmt,
      });
      if (teacherId) params.append("teacher_id", teacherId);
      if (batchId) params.append("batch_id", batchId);
      const res = await apiClient.get(
        `/api/v1/lectures/report/export?${params.toString()}`,
        { responseType: "blob" },
      );
      const disposition = res.headers["content-disposition"] as
        | string
        | undefined;
      const filename =
        disposition?.match(/filename="?([^"]+)"?/)?.[1] ?? "lecture-report";
      const url = window.URL.createObjectURL(res.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      onOpenChange(false);
    } catch {
      setError("Download failed. Check the date range and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        onOpenChange(isOpen);
        if (!isOpen) setError("");
      }}
    >
      <DialogPopup className="max-w-lg">
        <DialogTitle>Lecture Report</DialogTitle>
        <DialogDescription>
          Per-lecture export over a date range — schedule vs actual, who
          delivered and who recorded each entry. Excel or PDF.
        </DialogDescription>

        <div className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lr_start">From</Label>
              <Input
                id="lr_start"
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lr_end">To</Label>
              <Input
                id="lr_end"
                type="date"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lr_duration">Duration format</Label>
              <select
                id="lr_duration"
                value={durationStyle}
                onChange={(e) =>
                  setDurationStyle(e.target.value as "min" | "hhmm")
                }
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="min">Minutes</option>
                <option value="hhmm">Hours:Minutes</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lr_fmt">Format</Label>
              <select
                id="lr_fmt"
                value={fmt}
                onChange={(e) => setFmt(e.target.value as "xlsx" | "pdf")}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="xlsx">Excel</option>
                <option value="pdf">PDF</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lr_teacher">Teacher (optional)</Label>
              <select
                id="lr_teacher"
                value={teacherId}
                onChange={(e) => setTeacherId(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="">All teachers</option>
                {teachers.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lr_batch">Batch (optional)</Label>
              <select
                id="lr_batch"
                value={batchId}
                onChange={(e) => setBatchId(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="">All batches</option>
                {batches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => onOpenChange(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button onClick={handleDownload} disabled={busy}>
              {busy ? "Generating…" : "Download"}
            </Button>
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
