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
import type { ClassroomCreate } from "../_schemas/classroom";

interface CreateClassroomDialogProps {
  onSubmit: (data: Omit<ClassroomCreate, "branch_id">) => Promise<void> | void;
  isPending: boolean;
}

const EMPTY_FORM = {
  name: "",
  code: "",
  capacity: "30",
  floor: "",
};

export function CreateClassroomDialog({
  onSubmit,
  isPending,
}: CreateClassroomDialogProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState("");

  function reset() {
    setForm(EMPTY_FORM);
    setError("");
  }

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
        floor: form.floor || undefined,
      });
      reset();
      setOpen(false);
    } catch (err: any) {
      setError(
        err.response?.data?.error?.message || "Failed to create classroom"
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
        render={<Button onClick={() => setOpen(true)}>Create Classroom</Button>}
      />
      <DialogPopup>
        <DialogTitle>Create Classroom</DialogTitle>
        <DialogDescription>
          Add a physical or virtual room for offline / hybrid lectures.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="c_name">Name *</Label>
              <Input
                id="c_name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Room 101"
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="c_code">Code *</Label>
              <Input
                id="c_code"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                placeholder="e.g. R-101"
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="c_capacity">Capacity *</Label>
              <Input
                id="c_capacity"
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
              <Label htmlFor="c_floor">Floor</Label>
              <Input
                id="c_floor"
                value={form.floor}
                onChange={(e) => setForm({ ...form, floor: e.target.value })}
                placeholder="e.g. Ground, 1st"
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
              {isPending ? "Creating..." : "Create"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
