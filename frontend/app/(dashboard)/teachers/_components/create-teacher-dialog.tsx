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
import type { TeacherCreate } from "../_schemas/teacher";

interface CreateTeacherDialogProps {
  onSubmit: (data: Omit<TeacherCreate, "branch_id">) => Promise<void> | void;
  isPending: boolean;
}

const EMPTY_FORM = {
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  qualification: "",
};

export function CreateTeacherDialog({
  onSubmit,
  isPending,
}: CreateTeacherDialogProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState("");

  function reset() {
    setForm(EMPTY_FORM);
    setError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.first_name) {
      setError("First name is required");
      return;
    }
    try {
      await onSubmit({
        first_name: form.first_name,
        last_name: form.last_name,
        email: form.email || undefined,
        phone: form.phone || undefined,
        qualification: form.qualification || undefined,
      });
      reset();
      setOpen(false);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Failed to create teacher");
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
        render={<Button onClick={() => setOpen(true)}>Create Teacher</Button>}
      />
      <DialogPopup>
        <DialogTitle>Create Teacher</DialogTitle>
        <DialogDescription>Add a new teacher to this branch.</DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="t_first_name">First Name *</Label>
              <Input
                id="t_first_name"
                value={form.first_name}
                onChange={(e) =>
                  setForm({ ...form, first_name: e.target.value })
                }
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="t_last_name">Last Name</Label>
              <Input
                id="t_last_name"
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="t_email">Email</Label>
              <Input
                id="t_email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="t_phone">Phone</Label>
              <Input
                id="t_phone"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="t_qualification">Qualification</Label>
            <Input
              id="t_qualification"
              value={form.qualification}
              onChange={(e) =>
                setForm({ ...form, qualification: e.target.value })
              }
              placeholder="e.g. M.Sc Physics, B.Ed"
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
              {isPending ? "Creating..." : "Create"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
