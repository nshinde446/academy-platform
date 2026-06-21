"use client";

import { useEffect, useState } from "react";
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
import { studentKeys, useImportJob } from "../_hooks/use-students";
import type {
  ImportJob,
  ImportPreview,
  ImportUndoSummary,
} from "../_schemas/student";

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

// Optional override columns (design §5): if you already know a batch's course,
// length, and intake year, set them here and a newly-created batch uses them.
// Left blank, the batch falls back to Target-derived defaults (a 1-year course
// in the branch's current academic year).
const OPTIONAL_OVERRIDE_HEADERS = [
  "Course_opt",
  "Duration",
  "Academic_year",
  "Syllabus",
];

function downloadSampleTemplate() {
  const headers = [...SAMPLE_HEADERS, ...OPTIONAL_OVERRIDE_HEADERS];
  // First row shows a 2-year override; the rest leave the optional columns
  // empty so the example reads as "these are optional".
  const rows = SAMPLE_ROWS.map((r, i) =>
    i === 0
      ? [...r, "NEET 2-Year", "2 Years", "2025-2027", "NEET"]
      : [...r, "", "", "", ""],
  );
  downloadCsvTemplate("students-import-template.csv", headers, rows);
}

export function ImportStudentsDialog({ branchId }: ImportStudentsDialogProps) {
  const [open, setOpen] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [createMissing, setCreateMissing] = useState(true);
  const [jobId, setJobId] = useState<string | null>(null);
  const [undoing, setUndoing] = useState(false);
  const [undone, setUndone] = useState<ImportUndoSummary | null>(null);
  // Held in state (not just a ref) because the file <input> only renders in
  // step 1 — it unmounts once the preview shows, so we need the File to
  // survive into the import step.
  const [file, setFile] = useState<File | null>(null);
  const queryClient = useQueryClient();

  // The import runs as a background job; poll it for progress + the result.
  const jobQuery = useImportJob(branchId, jobId);
  const job = jobQuery.data ?? null;
  const finished = job?.job_status === "completed" ? job : null;
  const failed = job?.job_status === "failed";
  const processing =
    jobId !== null && job?.job_status !== "completed" && !failed;

  // When the job finishes, refresh the rosters / batches once.
  useEffect(() => {
    if (job?.job_status !== "completed") return;
    queryClient.invalidateQueries({ queryKey: studentKeys.list(branchId) });
    queryClient.invalidateQueries({ queryKey: studentKeys.withStats(branchId) });
    queryClient.invalidateQueries({ queryKey: studentKeys.roster(branchId) });
    if (job.batches_created.length > 0) {
      queryClient.invalidateQueries({ queryKey: ["batches"] });
    }
  }, [job?.job_status, job?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  function reset() {
    setError("");
    setPreview(null);
    setJobId(null);
    setCreateMissing(true);
    setUndone(null);
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

    setStarting(true);
    setError("");
    try {
      // Kick off a background job and switch to the progress view; the job
      // poll takes over from here, so a huge file never blocks the request.
      const res = await apiClient.post<ImportJob>(
        `/api/v1/students/import/start`,
        formData,
        {
          params: {
            branch_id: branchId,
            create_missing_batches: createMissing,
          },
          headers: { "Content-Type": "multipart/form-data" },
        },
      );
      setJobId(res.data.id);
      setPreview(null);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Import failed to start");
    } finally {
      setStarting(false);
    }
  }

  async function handleUndo() {
    if (!finished?.import_id) return;
    setUndoing(true);
    setError("");
    try {
      const res = await apiClient.post<ImportUndoSummary>(
        `/api/v1/students/import/${finished.import_id}/undo`,
        null,
        { params: { branch_id: branchId } },
      );
      queryClient.invalidateQueries({ queryKey: studentKeys.list(branchId) });
      queryClient.invalidateQueries({ queryKey: studentKeys.withStats(branchId) });
      queryClient.invalidateQueries({ queryKey: studentKeys.roster(branchId) });
      if (res.data.batches_deleted > 0) {
        queryClient.invalidateQueries({ queryKey: ["batches"] });
      }
      setUndone(res.data);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Undo failed");
    } finally {
      setUndoing(false);
    }
  }

  // The completed job is a superset of the old ImportSummary shape.
  const summary = finished;
  const hasSummary = summary !== null;
  const allImported =
    summary !== null && summary.skipped === 0 && summary.imported > 0;
  const allFailed =
    summary !== null && summary.imported === 0 && summary.skipped > 0;
  // Offer undo only while there's a handle and it hasn't been undone yet.
  const canUndo =
    summary !== null && summary.import_id !== null && undone === null;
  const pct =
    job && job.total_rows > 0
      ? Math.min(100, Math.round((job.processed_rows / job.total_rows) * 100))
      : 0;

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
          Phone, Parent Mobile, Gender, District, Caste, Username, RFIDNumber.{" "}
          To control how a <strong>new</strong> batch is built, also add{" "}
          <strong>Course_opt</strong> (course name),{" "}
          <strong>Duration</strong> (e.g. 1 Year / 2 Years),{" "}
          <strong>Academic_year</strong> (e.g. 2025-2027), and{" "}
          <strong>Syllabus</strong> (e.g. NEET / JEE / PCMB) — left blank,
          batches fall back to a 1-year course in the current year with subjects
          derived from Target.
        </DialogDescription>

        <div className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          {/* Step 1 — choose a file */}
          {!preview && !jobId && (
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
                  preview.rows_invalid_enrolment > 0 ||
                  preview.rows_invalid_consistency > 0 ||
                  preview.duplicate_rows > 0) && (
                  <p className="mt-1 text-xs text-amber-600">
                    {[
                      preview.rows_missing_name > 0 &&
                        `${preview.rows_missing_name} missing Name`,
                      preview.rows_invalid_enrolment > 0 &&
                        `${preview.rows_invalid_enrolment} invalid Class/Target`,
                      preview.rows_invalid_consistency > 0 &&
                        `${preview.rows_invalid_consistency} contradictory (e.g. 12th + 2-Year)`,
                      preview.duplicate_rows > 0 &&
                        `${preview.duplicate_rows} duplicate (already on file)`,
                    ]
                      .filter(Boolean)
                      .join(" · ")}{" "}
                    row(s) will be skipped.
                  </p>
                )}
                {preview.rows_with_warnings > 0 && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {preview.rows_with_warnings} row(s) have warnings (imported
                    anyway) — see the row notes below.
                  </p>
                )}
                {preview.new_academic_years.length > 0 && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Will create academic year(s):{" "}
                    <span className="font-medium">
                      {preview.new_academic_years.join(", ")}
                    </span>
                    .
                  </p>
                )}
              </div>

              {preview.blocking_error && (
                <p className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                  {preview.blocking_error}
                </p>
              )}

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
                            ) : b.creatable ? (
                              <span className="text-amber-600">
                                New → {b.suggested_course_code}
                                {b.suggested_exam_date
                                  ? ` (${b.suggested_exam_date})`
                                  : ""}
                              </span>
                            ) : (
                              <span className="text-destructive">
                                Can&apos;t create — {b.blocker}
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

              {preview.blocked_batches > 0 && (
                <p className="text-xs text-destructive">
                  {preview.blocked_batches} batch(es) can&apos;t be
                  auto-created (marked{" "}
                  <span className="font-medium">Can&apos;t create</span>{" "}
                  above). Create them on <span className="font-medium">
                    Batches
                  </span>{" "}
                  first, or add the academic year they need — rows pointing at
                  them will be skipped.
                </p>
              )}

              {preview.row_issues.length > 0 && (
                <ul className="max-h-32 overflow-y-auto list-disc rounded-lg border border-border pl-6 pr-2 py-2 text-xs text-muted-foreground">
                  {preview.row_issues.map((issue, i) => (
                    <li key={i}>{issue}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Step 3 — background job in progress */}
          {processing && (
            <div className="flex flex-col gap-2 rounded-lg border border-border p-3 text-sm">
              <p className="font-medium">
                Importing in the background
                {job && job.total_rows > 0 ? ` — ${pct}%` : "…"}
              </p>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-emerald-500 transition-all"
                  style={{ width: `${job && job.total_rows > 0 ? pct : 5}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                {job && job.total_rows > 0
                  ? `${job.processed_rows} of ${job.total_rows} rows processed`
                  : "Preparing…"}{" "}
                — you can close this dialog; the import keeps running.
              </p>
            </div>
          )}

          {/* Job failed */}
          {failed && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm">
              <p className="font-medium text-destructive">Import failed</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {job?.error_detail ||
                  "An unexpected error occurred. No rows were saved."}
              </p>
            </div>
          )}

          {/* Step 4 — import result */}
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
                  {summary.subjects_created > 0 &&
                    ` · ${summary.subjects_created} subject(s) for new course(s)`}
                </p>
              )}
              {summary.academic_years_created.length > 0 && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Created academic year(s):{" "}
                  {summary.academic_years_created.join(", ")}
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
              {summary.warnings.length > 0 && (
                <div className="mt-2 text-xs text-amber-600">
                  <p className="font-medium">
                    Imported with {summary.warnings.length} warning(s):
                  </p>
                  <ul className="list-disc pl-5">
                    {summary.warnings.slice(0, 10).map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                    {summary.warnings.length > 10 && (
                      <li>…and {summary.warnings.length - 10} more</li>
                    )}
                  </ul>
                </div>
              )}
              {undone && (
                <p className="mt-2 text-xs font-medium text-muted-foreground">
                  Undone — removed {undone.students_deleted} student(s)
                  {undone.batches_deleted > 0 &&
                    ` and ${undone.batches_deleted} auto-created batch(es)`}
                  {undone.subjects_deleted > 0 &&
                    ` and ${undone.subjects_deleted} subject(s)`}
                  .
                </p>
              )}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  {jobId ? "Close" : "Cancel"}
                </Button>
              }
            />

            {!preview && !jobId && (
              <Button onClick={handlePreview} disabled={previewing}>
                {previewing ? "Reading..." : "Preview import"}
              </Button>
            )}

            {preview && (
              <>
                <Button variant="outline" onClick={reset} type="button">
                  Back
                </Button>
                <Button
                  onClick={handleImport}
                  disabled={starting || !!preview.blocking_error}
                >
                  {starting ? "Starting..." : "Import"}
                </Button>
              </>
            )}

            {(hasSummary || failed) && (
              <Button onClick={reset} variant="outline">
                Upload another file
              </Button>
            )}

            {canUndo && (
              <Button
                onClick={handleUndo}
                disabled={undoing}
                variant="destructive"
              >
                {undoing ? "Undoing..." : "Undo import"}
              </Button>
            )}
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
