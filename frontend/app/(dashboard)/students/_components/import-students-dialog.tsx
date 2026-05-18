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
import { studentKeys } from "../_hooks/use-students";

interface ImportStudentsDialogProps {
  branchId: string;
}

export function ImportStudentsDialog({ branchId }: ImportStudentsDialogProps) {
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
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

    const formData = new FormData();
    formData.append("file", file);

    try {
      await apiClient.post(
        `/api/v1/students/import?branch_id=${branchId}`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      queryClient.invalidateQueries({ queryKey: studentKeys.list(branchId) });
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
        if (!isOpen) setError("");
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
          Upload a CSV or Excel file. Required column: Name. Optional: Roll No,
          Email, Phone, Parent Mobile, Gender, District, Caste, Username,
          RFIDNumber.
        </DialogDescription>
        <div className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" />
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
