"use client";

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogTrigger,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { downloadCsvTemplate } from "@/lib/csv-template";
import { studentKeys } from "../_hooks/use-students";
import type { ImportSummary } from "../_schemas/student";

interface ImportStudentsDialogProps {
  branchId: string;
}

// Per-row INPUT columns the student importer accepts (see
// backend/app/modules/student/services/import_service.py COLUMN_MAPPING).
// Class / Target / Batch are read per-row so a single file can mix
// cohorts. Sample covers every allowed Class and Target value so users
// have a working example of each combination.
const SAMPLE_HEADERS = [
  "Name",
  "Class",
  "Target",
  "Batch",
  "Roll No",
  "Email",
  "Phone",
  "Parent Mobile",
  "Gender",
  "District",
  "Caste",
  "Username",
  "RFIDNumber",
];

const SAMPLE_ROWS: string[][] = [
  [
    "Aman Sharma",
    "11",
    "NEET",
    "NEET-11-A",
    "S-001",
    "aman.sharma@example.edu",
    "9876543210",
    "9123456780",
    "M",
    "Pune",
    "General",
    "aman.sharma",
    "1234567890",
  ],
  [
    "Priya Singh",
    "12",
    "JEE-Main",
    "JEE-12-B",
    "S-002",
    "priya.singh@example.edu",
    "9876500000",
    "9123400000",
    "F",
    "Mumbai",
    "OBC",
    "priya.singh",
    "1234567891",
  ],
  [
    "Rohan Patel",
    "12",
    "JEE-Advanced",
    "JEE-12-A",
    "S-003",
    "rohan.patel@example.edu",
    "9876511111",
    "9123411111",
    "M",
    "Nashik",
    "General",
    "rohan.patel",
    "1234567892",
  ],
  [
    "Sneha Kulkarni",
    "Dropper",
    "Both",
    "NEET-DROP",
    "S-004",
    "sneha.kulkarni@example.edu",
    "9876522222",
    "9123422222",
    "F",
    "Pune",
    "SC",
    "sneha.kulkarni",
    "1234567893",
  ],
  [
    "Karan Mehta",
    "10",
    "Foundation",
    "FND-10",
    "S-005",
    "karan.mehta@example.edu",
    "9876533333",
    "9123433333",
    "M",
    "Aurangabad",
    "OBC",
    "karan.mehta",
    "1234567894",
  ],
  [
    "Ayesha Khan",
    "9",
    "Foundation",
    "FND-9",
    "S-006",
    "ayesha.khan@example.edu",
    "9876544444",
    "9123444444",
    "F",
    "Nagpur",
    "General",
    "ayesha.khan",
    "1234567895",
  ],
  [
    "Vikas Reddy",
    "11",
    "Other",
    "OTHER-11",
    "S-007",
    "vikas.reddy@example.edu",
    "9876555555",
    "9123455555",
    "M",
    "Solapur",
    "ST",
    "vikas.reddy",
    "1234567896",
  ],
];

function downloadSampleTemplate() {
  downloadCsvTemplate("students-import-template.csv", SAMPLE_HEADERS, SAMPLE_ROWS);
}

export function ImportStudentsDialog({ branchId }: ImportStudentsDialogProps) {
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  function reset() {
    setError("");
    setSummary(null);
    if (fileRef.current) fileRef.current.value = "";
  }

  async function handleUpload() {
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
      const res = await apiClient.post<ImportSummary>(
        `/api/v1/students/import`,
        formData,
        {
          params: { branch_id: branchId },
          headers: { "Content-Type": "multipart/form-data" },
        },
      );
      queryClient.invalidateQueries({ queryKey: studentKeys.list(branchId) });
      queryClient.invalidateQueries({ queryKey: studentKeys.withStats(branchId) });
      setSummary(res.data);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Import failed");
    } finally {
      setUploading(false);
    }
  }

  const hasResults = summary !== null;
  const allImported = summary !== null && summary.skipped === 0 && summary.imported > 0;
  const allFailed = summary !== null && summary.imported === 0 && summary.skipped > 0;

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        setOpen(isOpen);
        if (!isOpen) reset();
      }}
    >
      <DialogTrigger
        render={
          <Button variant="outline" onClick={() => setOpen(true)}>
            Import Students
          </Button>
        }
      />
      <DialogPopup>
        <DialogTitle>Import Students</DialogTitle>
        <DialogDescription>
          Upload a CSV or Excel file. <strong>Required:</strong> Name. Class /
          Target / Batch are per-row so one file can mix cohorts.{" "}
          <strong>Allowed Class:</strong> 9, 10, 11, 12, Dropper.{" "}
          <strong>Allowed Target:</strong> NEET, JEE-Main, JEE-Advanced, Both,
          Foundation, Other. <strong>Batch</strong> must match an existing
          batch <em>code</em> in this branch — create the batch first if it
          does not exist. Optional: Roll No, Email, Phone, Parent Mobile,
          Gender, District, Caste, Username, RFIDNumber.
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
            <div
              className={
                "rounded-lg border p-3 text-sm " +
                (allImported
                  ? "border-emerald-500/40 bg-emerald-500/10"
                  : allFailed
                    ? "border-destructive/40 bg-destructive/10"
                    : "border-amber-500/40 bg-amber-500/10")
              }
            >
              <p>
                <span className="font-medium">{summary.imported}</span> imported,{" "}
                <span className="font-medium">{summary.skipped}</span> skipped
                {allFailed && " — no rows were saved."}
                {!allImported && !allFailed && summary.imported > 0 &&
                  " — some rows were saved, others rejected."}
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

          {!hasResults && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="import_file">File *</Label>
              <Input
                id="import_file"
                ref={fileRef}
                type="file"
                accept=".csv,.xlsx,.xls"
              />
            </div>
          )}

          <div className="flex justify-end gap-2">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  {hasResults ? "Close" : "Cancel"}
                </Button>
              }
            />
            {!hasResults && (
              <Button onClick={handleUpload} disabled={uploading}>
                {uploading ? "Uploading..." : "Upload"}
              </Button>
            )}
            {hasResults && !allImported && (
              <Button onClick={reset} variant="outline">
                Upload another file
              </Button>
            )}
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
