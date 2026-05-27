"use client";

import { useRef, useState } from "react";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  CATEGORY_LABEL,
  CLASS_LABELS,
  EXAM_TYPE_LABEL,
  EXAM_TYPES,
  MATERIAL_CATEGORIES,
} from "../_schemas/material";
import type {
  ClassLabel,
  ExamType,
  MaterialCategory,
} from "../_schemas/material";
import {
  useAcademicYears,
  useBatches,
  useSubjects,
  useUploadMaterial,
} from "../_hooks/use-materials";

interface UploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  branchId: string | undefined;
  onUploaded?: (count: number) => void;
}

interface QueuedFile {
  id: string;
  file: File;
  topic: string;
  status: "queued" | "uploading" | "done" | "error";
  error?: string;
}

export function UploadDialog({
  open,
  onOpenChange,
  branchId,
  onUploaded,
}: UploadDialogProps) {
  const academicYears = useAcademicYears(branchId);
  const subjects = useSubjects(branchId);
  const batches = useBatches(branchId);
  const upload = useUploadMaterial(branchId);

  const [files, setFiles] = useState<QueuedFile[]>([]);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const [academicYearId, setAcademicYearId] = useState("");
  const [classLabel, setClassLabel] = useState<ClassLabel | "">("");
  const [subjectId, setSubjectId] = useState("");
  const [category, setCategory] = useState<MaterialCategory>("ncert");
  const [examTypes, setExamTypes] = useState<ExamType[]>([]);
  const [batchIds, setBatchIds] = useState<string[]>([]);
  const [description, setDescription] = useState("");

  function reset() {
    setFiles([]);
    setAcademicYearId("");
    setClassLabel("");
    setSubjectId("");
    setCategory("ncert");
    setExamTypes([]);
    setBatchIds([]);
    setDescription("");
  }

  function handleOpenChange(next: boolean) {
    if (!next && upload.isPending) return;
    if (!next) reset();
    onOpenChange(next);
  }

  function addFiles(list: FileList | null) {
    if (!list) return;
    const next: QueuedFile[] = Array.from(list).map((f) => ({
      id: `${f.name}-${f.size}-${f.lastModified}-${Math.random()}`,
      file: f,
      topic: "",
      status: "queued",
    }));
    setFiles((prev) => [...prev, ...next]);
  }

  function removeFile(id: string) {
    setFiles((prev) => prev.filter((q) => q.id !== id));
  }

  function toggleExam(et: ExamType) {
    setExamTypes((prev) =>
      prev.includes(et) ? prev.filter((x) => x !== et) : [...prev, et],
    );
  }

  function toggleBatch(id: string) {
    setBatchIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  const canSubmit =
    files.length > 0 &&
    files.some((f) => f.status !== "done") &&
    academicYearId &&
    classLabel &&
    subjectId &&
    category &&
    !upload.isPending;

  async function submit() {
    if (!canSubmit) return;
    let uploaded = 0;
    for (const q of files) {
      if (q.status === "done") continue;
      setFiles((prev) =>
        prev.map((p) => (p.id === q.id ? { ...p, status: "uploading" } : p)),
      );
      try {
        await upload.mutateAsync({
          file: q.file,
          fields: {
            academic_year_id: academicYearId,
            class_label: classLabel,
            subject_id: subjectId,
            category,
            exam_types: examTypes,
            topic: q.topic || undefined,
            description: description || undefined,
            batch_ids: batchIds.length > 0 ? batchIds : undefined,
          },
        });
        uploaded += 1;
        setFiles((prev) =>
          prev.map((p) => (p.id === q.id ? { ...p, status: "done" } : p)),
        );
      } catch (err: unknown) {
        const msg =
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ?? "Upload failed";
        setFiles((prev) =>
          prev.map((p) =>
            p.id === q.id ? { ...p, status: "error", error: msg } : p,
          ),
        );
      }
    }
    if (uploaded > 0) {
      onUploaded?.(uploaded);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogPopup className="max-w-2xl">
        <DialogTitle>Upload study materials</DialogTitle>
        <DialogDescription>
          Drop one or many files. Tags apply to every file in this upload.
        </DialogDescription>

        <div className="mt-4 flex flex-col gap-4">
          {/* Drop zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              addFiles(e.dataTransfer.files);
            }}
            className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-6 text-sm transition-colors ${
              dragOver
                ? "border-primary bg-primary/5"
                : "border-border bg-muted/20"
            }`}
          >
            <p className="text-muted-foreground">
              Drop PDFs / images / docs here, or
            </p>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => fileInput.current?.click()}
            >
              Browse files
            </Button>
            <input
              ref={fileInput}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => addFiles(e.target.files)}
            />
          </div>

          {files.length > 0 && (
            <div className="flex max-h-40 flex-col gap-1 overflow-y-auto rounded-md border p-2 text-[12.5px]">
              {files.map((q) => (
                <div key={q.id} className="flex items-center gap-2">
                  <span className="truncate">{q.file.name}</span>
                  <span className="ml-auto shrink-0 text-muted-foreground">
                    {(q.file.size / 1024).toFixed(0)} KB
                  </span>
                  <span
                    className={`shrink-0 text-[10.5px] uppercase tracking-wide ${
                      q.status === "done"
                        ? "text-success"
                        : q.status === "error"
                          ? "text-destructive"
                          : "text-muted-foreground"
                    }`}
                    title={q.error}
                  >
                    {q.status === "queued" ? "" : q.status}
                  </span>
                  {q.status !== "uploading" && (
                    <button
                      type="button"
                      onClick={() => removeFile(q.id)}
                      className="text-muted-foreground hover:text-foreground"
                      aria-label="Remove"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Tag form */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="flex flex-col gap-1">
              <Label>Academic year</Label>
              <select
                className="rounded-md border bg-background px-2 py-1.5 text-sm"
                value={academicYearId}
                onChange={(e) => setAcademicYearId(e.target.value)}
              >
                <option value="">— select —</option>
                {(academicYears.data ?? []).map((ay) => (
                  <option key={ay.id} value={ay.id}>
                    {ay.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <Label>Class</Label>
              <select
                className="rounded-md border bg-background px-2 py-1.5 text-sm"
                value={classLabel}
                onChange={(e) => setClassLabel(e.target.value as ClassLabel)}
              >
                <option value="">— select —</option>
                {CLASS_LABELS.map((c) => (
                  <option key={c} value={c}>
                    {c === "drop" ? "Drop year" : `Class ${c}`}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <Label>Subject</Label>
              <select
                className="rounded-md border bg-background px-2 py-1.5 text-sm"
                value={subjectId}
                onChange={(e) => setSubjectId(e.target.value)}
              >
                <option value="">— select —</option>
                {(subjects.data ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <Label>Category</Label>
              <select
                className="rounded-md border bg-background px-2 py-1.5 text-sm"
                value={category}
                onChange={(e) =>
                  setCategory(e.target.value as MaterialCategory)
                }
              >
                {MATERIAL_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {CATEGORY_LABEL[c]}
                  </option>
                ))}
              </select>
            </div>

            <div className="col-span-2 flex flex-col gap-1">
              <Label>Exam types</Label>
              <div className="flex flex-wrap gap-1.5">
                {EXAM_TYPES.map((et) => (
                  <button
                    key={et}
                    type="button"
                    onClick={() => toggleExam(et)}
                    className={`rounded-full border px-2 py-0.5 text-[12px] transition-colors ${
                      examTypes.includes(et)
                        ? "border-primary bg-primary/10"
                        : "border-border text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    {EXAM_TYPE_LABEL[et]}
                  </button>
                ))}
              </div>
            </div>

            {(batches.data?.length ?? 0) > 0 && (
              <div className="col-span-2 flex flex-col gap-1">
                <Label>Link to batches (optional)</Label>
                <div className="flex flex-wrap gap-1.5">
                  {(batches.data ?? []).map((b) => (
                    <button
                      key={b.id}
                      type="button"
                      onClick={() => toggleBatch(b.id)}
                      className={`rounded-full border px-2 py-0.5 text-[12px] transition-colors ${
                        batchIds.includes(b.id)
                          ? "border-primary bg-primary/10"
                          : "border-border text-muted-foreground hover:bg-muted"
                      }`}
                    >
                      {b.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="col-span-2 flex flex-col gap-1">
              <Label>Description (optional)</Label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. 2024 NEET PYQ compilation"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <DialogClose
              render={
                <Button variant="outline" type="button" disabled={upload.isPending}>
                  Close
                </Button>
              }
            />
            <Button onClick={submit} disabled={!canSubmit} type="button">
              {upload.isPending
                ? "Uploading…"
                : `Upload ${files.filter((f) => f.status !== "done").length || ""}`}
            </Button>
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
