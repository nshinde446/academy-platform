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
import { teacherKeys } from "../_hooks/use-teachers";
import type { ImportSummary } from "../_schemas/teacher";

interface ImportTeachersDialogProps {
  branchId: string;
}

export function ImportTeachersDialog({ branchId }: ImportTeachersDialogProps) {
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

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
        `/api/v1/teachers/import?branch_id=${branchId}`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      queryClient.invalidateQueries({ queryKey: teacherKeys.list(branchId) });
      setSummary(res.data);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Import failed");
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
            Import Teachers
          </Button>
        }
      />
      <DialogPopup>
        <DialogTitle>Import Teachers</DialogTitle>
        <DialogDescription>
          Upload a CSV or Excel file. Required column: Name. Optional: Email,
          Phone, Qualification, Subjects (comma-separated subject names —
          matched to existing subjects in this branch).
        </DialogDescription>
        <div className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}
          {summary && (
            <div className="rounded-lg border bg-muted/40 p-3 text-sm">
              <p>
                <span className="font-medium">{summary.imported}</span> imported,{" "}
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
                {uploading ? "Uploading..." : "Upload"}
              </Button>
            )}
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
