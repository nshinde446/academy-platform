"use client";

import { useState } from "react";
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
import type { ImportPreview, ImportSummary } from "../_schemas/student";

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
  [
    "Tanvi Joshi",
    "12",
    "MHT-CET",
    "MHT-12-A",
    "S-008",
    "tanvi.joshi@example.edu",
    "9876566666",
    "9123466666",
    "F",
    "Pune",
    "OBC",
    "tanvi.joshi",
    "1234567897",
  ],
];

function downloadSampleTemplate() {
  downloadCsvTemplate("students-import-template.csv", SAMPLE_HEADERS, SAMPLE_ROWS);
}

export function ImportStudentsDialog({ branchId }: ImportStudentsDialogProps) {
  const [open, setOpen] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [createMissing, setCreateMissing] = useState(true);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  // Held in state (not just a ref) because the file <input> only renders in
  // step 1 — it unmounts once the preview shows, so we need the File to
  // survive into the import step.
  const [file, setFile] = useState<File | null>(null);
  const queryClient = useQueryClient();

  function reset() {
    setError("");
    setPreview(null);
    setSummary(null);
    setCreateMissing(true);
    setFile(null);
  }

  function buildFormData(): FormData | null {
    if (!file) {
      setError("Please select a file.");
      return null;
    }
    const formData = new FormData();
    formData.append("file", file);
    return formData;
  }

  async function handlePreview() {
    const formData = buildFormData();
    if (!formData) return;

    setPreviewing(true);
    setError("");
    try {
      const res = await apiClient.post<ImportPreview>(
        `/api/v1/students/import/preview`,
        formData,
        {
          params: { branch_id: branchId },
          headers: { "Content-Type": "multipart/form-data" },
        },
      );
      setPreview(res.data);
      setCreateMissing(res.data.missing_batches > 0);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Could not read the file");
    } finally {
      setPreviewing(false);
    }
  }

  async function handleImport() {
    const formData = buildFormData();
    if (!formData) return;

    setUploading(true);
    setError("");
    try {
      const res = await apiClient.post<ImportSummary>(
        `/api/v1/students/import`,
        formData,
        {
          params: {
            branch_id: branchId,
            create_missing_batches: createMissing,
          },
          headers: { "Content-Type": "multipart/form-data" },
        },
      );
      queryClient.invalidateQueries({ queryKey: studentKeys.list(branchId) });
      queryClient.invalidateQueries({ queryKey: studentKeys.withStats(branchId) });
      if (res.data.batches_created.length > 0) {
        queryClient.invalidateQueries({ queryKey: ["batches"] });
      }
      setSummary(res.data);
      setPreview(null);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Import failed");
    } finally {
      setUploading(false);
    }
  }

  const hasSummary = summary !== null;
  const allImported =
    summary !== null && summary.skipped === 0 && summary.imported > 0;
  const allFailed =
    summary !== null && summary.imported === 0 && summary.skipped > 0;

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
          <strong>Allowed Target:</strong> NEET, JEE-Main, JEE-Advanced,
          MHT-CET, Both, Foundation, Other. You&apos;ll see a preview of which{" "}
          <strong>batches</strong> already exist before anything is saved — any
          that are missing can be created for you. Optional: Roll No, Email,
          Phone, Parent Mobile, Gender, District, Caste, Username, RFIDNumber.
        </DialogDescription>

        <div className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          {/* Step 1 — choose a file */}
          {!preview && !hasSummary && (
            <>
              <div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={downloadSampleTemplate}
                >
                  Download sample CSV
                </Button>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="import_file">File *</Label>
                <Input
                  id="import_file"
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
            </>
          )}

          {/* Step 2 — preview the batch split */}
          {preview && (
            <div className="flex flex-col gap-3">
              <div className="rounded-lg border border-border p-3 text-sm">
                <p>
                  <span className="font-medium">{preview.total_rows}</span>{" "}
                  rows ·{" "}
                  <span className="font-medium">
                    {preview.importable_rows}
                  </span>{" "}
                  importable ·{" "}
                  <span className="font-medium">
                    {preview.existing_batches}
                  </span>{" "}
                  batches matched ·{" "}
                  <span className="font-medium">
                    {preview.missing_batches}
                  </span>{" "}
                  missing
                </p>
                {(preview.rows_missing_name > 0 ||
                  preview.rows_invalid_enrolment > 0) && (
                  <p className="mt-1 text-xs text-amber-600">
                    {preview.rows_missing_name > 0 &&
                      `${preview.rows_missing_name} row(s) missing Name`}
                    {preview.rows_missing_name > 0 &&
                      preview.rows_invalid_enrolment > 0 &&
                      " · "}
                    {preview.rows_invalid_enrolment > 0 &&
                      `${preview.rows_invalid_enrolment} row(s) with an invalid Class/Target`}{" "}
                    will be skipped.
                  </p>
                )}
              </div>

              {preview.batches.length > 0 && (
                <div className="max-h-52 overflow-y-auto rounded-lg border border-border text-xs">
                  <table className="w-full">
                    <thead className="sticky top-0 bg-muted text-left text-muted-foreground">
                      <tr>
                        <th className="px-2 py-1 font-medium">Batch</th>
                        <th className="px-2 py-1 font-medium">Students</th>
                        <th className="px-2 py-1 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.batches.map((b) => (
                        <tr key={b.code} className="border-t border-border">
                          <td className="px-2 py-1 font-mono">{b.code}</td>
                          <td className="px-2 py-1">{b.student_count}</td>
                          <td className="px-2 py-1">
                            {b.exists ? (
                              <span className="text-emerald-600">Exists</span>
                            ) : (
                              <span className="text-amber-600">
                                New → {b.suggested_course_code}
                                {b.suggested_exam_date
                                  ? ` (${b.suggested_exam_date})`
                                  : ""}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {preview.missing_batches > 0 && (
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={createMissing}
                    onChange={(e) => setCreateMissing(e.target.checked)}
                  />
                  <span>
                    Create the {preview.missing_batches} missing batch(es) and
                    assign students. Course &amp; exam date are derived from
                    each batch&apos;s Target — you can edit them later on{" "}
                    <span className="font-medium">Batches</span>. If unchecked,
                    rows pointing at a missing batch are skipped.
                  </span>
                </label>
              )}
            </div>
          )}

          {/* Step 3 — import result */}
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
                <span className="font-medium">{summary.imported}</span>{" "}
                imported, <span className="font-medium">{summary.skipped}</span>{" "}
                skipped
                {allFailed && " — no rows were saved."}
                {!allImported &&
                  !allFailed &&
                  summary.imported > 0 &&
                  " — some rows were saved, others rejected."}
              </p>
              {summary.batches_created.length > 0 && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Created {summary.batches_created.length} batch(es):{" "}
                  {summary.batches_created.join(", ")}
                </p>
              )}
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

          <div className="flex justify-end gap-2">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  {hasSummary ? "Close" : "Cancel"}
                </Button>
              }
            />

            {!preview && !hasSummary && (
              <Button onClick={handlePreview} disabled={previewing}>
                {previewing ? "Reading..." : "Preview import"}
              </Button>
            )}

            {preview && (
              <>
                <Button variant="outline" onClick={reset} type="button">
                  Back
                </Button>
                <Button onClick={handleImport} disabled={uploading}>
                  {uploading ? "Importing..." : "Import"}
                </Button>
              </>
            )}

            {hasSummary && !allImported && (
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
