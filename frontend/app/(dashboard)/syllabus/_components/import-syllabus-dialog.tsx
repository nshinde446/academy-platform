"use client";

import { useState } from "react";
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
import type {
  CourseOption,
  SyllabusImportSummary,
} from "../_schemas/syllabus";

interface ImportSyllabusDialogProps {
  courses: CourseOption[];
  defaultCourseId?: string;
  onImport: (params: {
    courseId: string;
    file: File;
  }) => Promise<SyllabusImportSummary>;
  isPending: boolean;
}

export function ImportSyllabusDialog({
  courses,
  defaultCourseId,
  onImport,
  isPending,
}: ImportSyllabusDialogProps) {
  const [open, setOpen] = useState(false);
  const [courseId, setCourseId] = useState(defaultCourseId ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [summary, setSummary] = useState<SyllabusImportSummary | null>(null);
  const [error, setError] = useState("");

  function reset() {
    setFile(null);
    setSummary(null);
    setError("");
    setCourseId(defaultCourseId ?? "");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSummary(null);
    if (!courseId) {
      setError("Pick a course");
      return;
    }
    if (!file) {
      setError("Pick an .xlsx file");
      return;
    }
    if (!file.name.toLowerCase().endsWith(".xlsx")) {
      setError("Only .xlsx is supported by the import endpoint");
      return;
    }

    try {
      const result = await onImport({ courseId, file });
      setSummary(result);
    } catch (err: any) {
      setError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          err?.message ||
          "Import failed"
      );
    }
  }

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
          <Button onClick={() => setOpen(true)} disabled={courses.length === 0}>
            Import Syllabus
          </Button>
        }
      />
      <DialogPopup>
        <DialogTitle>Import Syllabus</DialogTitle>
        <DialogDescription>
          Upload an .xlsx with columns:{" "}
          <code>Subject</code>, <code>Chapter</code>, <code>Topic</code>,{" "}
          <code>Subtopic</code> (optional). Existing nodes are reused —
          re-importing the same file is safe.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="import_course">Course *</Label>
            <select
              id="import_course"
              value={courseId}
              onChange={(e) => setCourseId(e.target.value)}
              className="flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm"
              required
            >
              <option value="">Select a course...</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.code})
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="import_file">File (.xlsx) *</Label>
            <Input
              id="import_file"
              type="file"
              accept=".xlsx"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
            />
            {file && (
              <span className="text-xs text-muted-foreground">
                {file.name} ({Math.round(file.size / 1024)} KB)
              </span>
            )}
          </div>

          {summary && (
            <div
              data-testid="import-summary"
              className="rounded-md border bg-muted/30 p-3 text-sm"
            >
              <p className="font-medium">Import complete</p>
              <ul className="mt-1 text-muted-foreground">
                <li>Rows processed: {summary.rows_processed}</li>
                <li>Subjects created: {summary.subjects_created}</li>
                <li>Chapters created: {summary.chapters_created}</li>
                <li>Topics created: {summary.topics_created}</li>
                <li>Subtopics created: {summary.subtopics_created}</li>
              </ul>
              {summary.errors.length > 0 && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-destructive">
                    {summary.errors.length} row error
                    {summary.errors.length === 1 ? "" : "s"}
                  </summary>
                  <ul className="mt-1 list-disc pl-4 text-xs text-destructive">
                    {summary.errors.slice(0, 20).map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  {summary ? "Close" : "Cancel"}
                </Button>
              }
            />
            <Button type="submit" disabled={isPending}>
              {isPending ? "Importing..." : summary ? "Import again" : "Import"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
