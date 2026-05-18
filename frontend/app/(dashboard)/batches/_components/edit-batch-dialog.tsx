"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import type { BatchResponse, BatchUpdate } from "../_schemas/batch";

interface EditBatchDialogProps {
  batch: BatchResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: BatchUpdate) => Promise<void> | void;
  isPending: boolean;
}

function buildForm(b: BatchResponse | null) {
  return {
    name: b?.name ?? "",
    code: b?.code ?? "",
    capacity: b ? String(b.capacity) : "30",
  };
}

export function EditBatchDialog({
  batch,
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: EditBatchDialogProps) {
  const [form, setForm] = useState(() => buildForm(batch));
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setForm(buildForm(batch));
      setError("");
    }
  }, [open, batch]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name || !form.code) {
      setError("Batch name and code are required");
      return;
    }
    const capacity = parseInt(form.capacity, 10);
    if (!Number.isFinite(capacity) || capacity < 1) {
      setError("Capacity must be at least 1");
      return;
    }

    try {
      await onSubmit({
        name: form.name,
        code: form.code,
        capacity,
      });
      onOpenChange(false);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Failed to update batch");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>Edit Batch</DialogTitle>
        <DialogDescription>
          Update the batch fields. Course and academic year range can't be
          changed after creation.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit_batch_name">Batch Name *</Label>
              <Input
                id="edit_batch_name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit_batch_code">Batch Code *</Label>
              <Input
                id="edit_batch_code"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5 sm:max-w-[calc(50%-0.375rem)]">
            <Label htmlFor="edit_batch_capacity">Capacity</Label>
            <Input
              id="edit_batch_capacity"
              type="number"
              min={1}
              value={form.capacity}
              onChange={(e) => setForm({ ...form, capacity: e.target.value })}
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  Cancel
                </Button>
              }
            />
            <Button type="submit" disabled={isPending}>
              {isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
