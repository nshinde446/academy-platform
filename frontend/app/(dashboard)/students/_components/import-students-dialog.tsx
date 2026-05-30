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

interface ImportStudentsDialogProps {
  branchId: string;
}

// Per-row INPUT columns the student importer accepts (see
// backend/app/modules/student/services/import_service.py COLUMN_MAPPING).
// Class / Target / Batch are now read per-row so a single file can mix
// cohorts. Table-view derived columns (Rank, Avg score, Attendance,
// DPP, Fees, Actions) are computed by the system and intentionally
// absent.
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
    "",
    "F",
    "Mumbai",
    "",
    "priya.singh",
    "",
  ],
];

function downloadSampleTemplate() {
  downloadCsvTemplate("students-import-template.csv", SAMPLE_HEADERS, SAMPLE_ROWS);
}

export function ImportStudentsDialog({ branchId }: ImportStudentsDialogProps) {
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  function reset() {
    setError("");
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

    const formData = new FormData();
    formData.append("file", file);

    try {
      await apiClient.post(
        `/api/v1/students/import`,
        formData,
        {
          params: { branch_id: branchId },
          headers: { "Content-Type": "multipart/form-data" },
        },
      );
      queryClient.invalidateQueries({ queryKey: studentKeys.list(branchId) });
      reset();
      setOpen(false);
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
          Upload a CSV or Excel file. Required columns: Name, Class, Target,
          Batch. Optional: Roll No, Email, Phone, Parent Mobile, Gender,
          District, Caste, Username, RFIDNumber. Class / Target / Batch are
          per-row, so one file can mix cohorts.
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

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="import_file">File *</Label>
            <Input
              id="import_file"
              ref={fileRef}
              type="file"
              accept=".csv,.xlsx,.xls"
            />
          </div>

          <div className="flex justify-end gap-2">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  Cancel
                </Button>
              }
            />
            <Button onClick={handleUpload} disabled={uploading}>
              {uploading ? "Uploading..." : "Upload"}
            </Button>
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
