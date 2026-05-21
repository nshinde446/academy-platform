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
import type {
  ClassroomResponse,
  ClassroomUpdate,
} from "../_schemas/classroom";

interface EditClassroomDialogProps {
  classroom: ClassroomResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: ClassroomUpdate) => Promise<void> | void;
  isPending: boolean;
}

function buildForm(c: ClassroomResponse | null) {
  return {
    name: c?.name ?? "",
    code: c?.code ?? "",
    capacity: c?.capacity != null ? String(c.capacity) : "30",
    floor: c?.floor ?? "",
  };
}

export function EditClassroomDialog({
  classroom,
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: EditClassroomDialogProps) {
  const [form, setForm] = useState(() => buildForm(classroom));
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setForm(buildForm(classroom));
      setError("");
    }
  }, [open, classroom]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name || !form.code) {
      setError("Name and code are required");
      return;
    }
    const capacity = parseInt(form.capacity, 10);
    if (Number.isNaN(capacity) || capacity <= 0) {
      setError("Capacity must be a positive number");
      return;
    }
    try {
      await onSubmit({
        name: form.name,
        code: form.code,
        capacity,
        floor: form.floor || null,
      });
      onOpenChange(false);
    } catch (err: any) {
      setError(
        err.response?.data?.error?.message || "Failed to update classroom"
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>Edit Classroom</DialogTitle>
        <DialogDescription>Update the fields and save.</DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ec_name">Name *</Label>
              <Input
                id="ec_name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ec_code">Code *</Label>
              <Input
                id="ec_code"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ec_capacity">Capacity *</Label>
              <Input
                id="ec_capacity"
                type="number"
                min="1"
                value={form.capacity}
                onChange={(e) =>
                  setForm({ ...form, capacity: e.target.value })
                }
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ec_floor">Floor</Label>
              <Input
                id="ec_floor"
                value={form.floor}
                onChange={(e) => setForm({ ...form, floor: e.target.value })}
              />
            </div>
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
