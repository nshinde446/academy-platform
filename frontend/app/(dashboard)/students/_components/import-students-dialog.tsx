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
import { studentKeys } from "../_hooks/use-students";
import {
  STANDARDS,
  TARGET_EXAMS,
  type Standard,
  type TargetExam,
} from "../_schemas/student";

interface ImportStudentsDialogProps {
  branchId: string;
}

const SELECT_CLASS =
  "flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

export function ImportStudentsDialog({ branchId }: ImportStudentsDialogProps) {
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [standard, setStandard] = useState<Standard | "">("");
  const [targetExam, setTargetExam] = useState<TargetExam | "">("");
  const fileRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  function reset() {
    setError("");
    setStandard("");
    setTargetExam("");
    if (fileRef.current) fileRef.current.value = "";
  }

  async function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Please select a file.");
      return;
    }
    if (!standard) {
      setError("Pick the Standard / Class for these students.");
      return;
    }
    if (!targetExam) {
      setError("Pick the target exam track for these students.");
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
          params: {
            branch_id: branchId,
            standard,
            target_exam: targetExam,
          },
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
          Upload a CSV or Excel file. Required column: Name. Optional: Roll
          No, Email, Phone, Parent Mobile, Gender, District, Caste, Username,
          RFIDNumber. Standard and target exam apply to every row in the
          file.
        </DialogDescription>
        <div className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="import_standard">Standard *</Label>
              <select
                id="import_standard"
                value={standard}
                onChange={(e) => setStandard(e.target.value as Standard)}
                className={SELECT_CLASS}
                required
              >
                <option value="">Pick standard…</option>
                {STANDARDS.map((s) => (
                  <option key={s} value={s}>
                    {s === "Dropper" ? "Dropper" : `Class ${s}`}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="import_target_exam">Target exam *</Label>
              <select
                id="import_target_exam"
                value={targetExam}
                onChange={(e) =>
                  setTargetExam(e.target.value as TargetExam)
                }
                className={SELECT_CLASS}
                required
              >
                <option value="">Pick target exam…</option>
                {TARGET_EXAMS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
          </div>

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
