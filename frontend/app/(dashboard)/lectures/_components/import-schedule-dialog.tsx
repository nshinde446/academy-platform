"use client";

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogTrigger,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { downloadCsvTemplate } from "@/lib/csv-template";
import { lectureKeys } from "../_hooks/use-lectures";

interface ImportScheduleSummary {
  imported: number;
  skipped: number;
  errors: string[];
}

// Per-row INPUT columns the lecture importer reads (see
// backend/app/modules/lectures/services/import_service.py). Derived
// values (status, conducted_at, etc.) don't belong in the template.
const SAMPLE_HEADERS = [
  "date",
  "start_time",
  "end_time",
  "teacher_email",
  "batch_code",
  "subject_code",
  "classroom_code",
  "delivery_mode",
  "notes",
];

// Two example rows so the admin can see what real values look like for
// the optional columns alongside the required ones. example.edu emails
// so nothing looks like a real address.
const SAMPLE_ROWS: string[][] = [
  [
    "2026-06-01",
    "09:00",
    "10:00",
    "rahul.sharma@example.edu",
    "NEET-A",
    "PHY",
    "R-101",
    "offline",
    "Newton's laws of motion",
  ],
  [
    "2026-06-01",
    "10:15",
    "11:15",
    "priya.menon@example.edu",
    "JEE-B",
    "MATH",
    "",
    "online",
    "",
  ],
];

function downloadSampleTemplate() {
  downloadCsvTemplate(
    "lecture-schedule-template.csv",
    SAMPLE_HEADERS,
    SAMPLE_ROWS,
  );
}

interface ImportScheduleDialogProps {
  branchId: string | undefined;
}

export function ImportScheduleDialog({ branchId }: ImportScheduleDialogProps) {
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<ImportScheduleSummary | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  async function handleUpload() {
    if (!branchId) {
      setError("No branch selected.");
      return;
    }
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Please select a file.");
      return;
    }

    setUploading(true);
    setError("");
    setSummary(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await apiClient.post<ImportScheduleSummary>(
        `/api/v1/lectures/import?branch_id=${branchId}`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      queryClient.invalidateQueries({ queryKey: lectureKeys.list(branchId) });
      setSummary(res.data);
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          err.response?.data?.error?.message ||
          "Import failed",
      );
    } finally {
      setUploading(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        setOpen(isOpen);
        if (!isOpen) {
          setError("");
          setSummary(null);
        }
      }}
    >
      <DialogTrigger
        render={
          <Button variant="outline" onClick={() => setOpen(true)}>
            Import schedule
          </Button>
        }
      />
      <DialogPopup>
        <DialogTitle>Import lecture schedule</DialogTitle>
        <DialogDescription>
          Upload a CSV or Excel sheet with the week&apos;s schedule. Required
          columns:{" "}
          <span className="font-mono text-xs">
            date, start_time, end_time, teacher_email, batch_code, subject_code
          </span>
          . Optional: <span className="font-mono text-xs">classroom_code</span>,{" "}
          <span className="font-mono text-xs">delivery_mode</span>,{" "}
          <span className="font-mono text-xs">notes</span>. Rows that fail
          validation are skipped — you&apos;ll get a list of which ones and why.
        </DialogDescription>
        <div className="mt-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={downloadSampleTemplate}
          >
            Download sample CSV
          </Button>
        </div>
        <div className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}
          {summary && (
            <div className="rounded-lg border bg-muted/40 p-3 text-sm">
              <p>
                <span className="font-medium text-[var(--success)]">
                  {summary.imported}
                </span>{" "}
                imported,{" "}
                <span className="font-medium">{summary.skipped}</span> skipped
              </p>
              {summary.errors.length > 0 && (
                <ul className="mt-2 list-disc pl-5 text-xs text-muted-foreground">
                  {summary.errors.slice(0, 10).map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                  {summary.errors.length > 10 && (
                    <li>…and {summary.errors.length - 10} more</li>
                  )}
                </ul>
              )}
            </div>
          )}
          <Input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" />
          <p className="text-[11px] text-muted-foreground">
            Date format: YYYY-MM-DD. Times in 24h HH:MM. Teachers matched by
            their account email; batches and subjects matched by code.
          </p>
          <div className="flex justify-end gap-2">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  {summary ? "Close" : "Cancel"}
                </Button>
              }
            />
            {!summary && (
              <Button onClick={handleUpload} disabled={uploading}>
                {uploading ? "Uploading…" : "Upload"}
              </Button>
            )}
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
