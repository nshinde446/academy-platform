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
import { apiErrorMessage } from "@/lib/api-error";
import { staffKeys } from "../_hooks/use-staff";
import type { ImportSummary } from "../_schemas/staff";

const SAMPLE_HEADERS = ["EmpCode", "Name", "Department", "Designation"];
const SAMPLE_ROWS: string[][] = [
  ["1", "Mr. Bhagvat Dhesale", "MSA-Teachers", "Teacher"],
  ["2", "Mr. Ram Wable", "MSA-Accounts", "Accounts"],
  ["81", "Mr. Vikas Security", "Security", "Security Admin"],
];

export function ImportStaffDialog({ branchId }: { branchId: string }) {
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();

  async function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return setError("Please select a file.");
    setUploading(true);
    setError("");
    setSummary(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await apiClient.post<ImportSummary>(
        `/api/v1/staff/import?branch_id=${branchId}`,
        fd,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      qc.invalidateQueries({ queryKey: staffKeys.all });
      setSummary(res.data);
    } catch (err) {
      setError(apiErrorMessage(err, "Import failed"));
    } finally {
      setUploading(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) {
          setError("");
          setSummary(null);
        }
      }}
    >
      <DialogTrigger
        render={
          <Button variant="outline" onClick={() => setOpen(true)}>
            Import Staff
          </Button>
        }
      />
      <DialogPopup>
        <DialogTitle>Import Staff</DialogTitle>
        <DialogDescription>
          Upload a CSV or Excel file. Columns: EmpCode (optional — auto-allocated
          when blank), Name, Department (must match a department name),
          Designation. Existing codes are kept as legacy; new joiners follow the
          department range.
        </DialogDescription>
        <div className="mt-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              downloadCsvTemplate("staff-import-template.csv", SAMPLE_HEADERS, SAMPLE_ROWS)
            }
          >
            Download sample CSV
          </Button>
        </div>
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
                {uploading ? "Uploading…" : "Upload"}
              </Button>
            )}
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
