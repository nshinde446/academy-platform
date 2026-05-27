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
import type { TeacherResponse, TeacherUpdate } from "../_schemas/teacher";

interface EditTeacherDialogProps {
  teacher: TeacherResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: TeacherUpdate) => Promise<void> | void;
  isPending: boolean;
}

function buildForm(t: TeacherResponse | null) {
  return {
    first_name: t?.first_name ?? "",
    last_name: t?.last_name ?? "",
    email: t?.email ?? "",
    phone: t?.phone ?? "",
    qualification: t?.qualification ?? "",
    years_experience:
      t?.years_experience != null ? String(t.years_experience) : "",
  };
}

export function EditTeacherDialog({
  teacher,
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: EditTeacherDialogProps) {
  const [form, setForm] = useState(() => buildForm(teacher));
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setForm(buildForm(teacher));
      setError("");
    }
  }, [open, teacher]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.first_name) {
      setError("First name is required");
      return;
    }
    try {
      const years = form.years_experience.trim();
      await onSubmit({
        first_name: form.first_name,
        last_name: form.last_name || null,
        email: form.email || null,
        phone: form.phone || null,
        qualification: form.qualification || null,
        years_experience: years === "" ? null : Number(years),
      });
      onOpenChange(false);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Failed to update teacher");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>Edit Teacher</DialogTitle>
        <DialogDescription>Update the fields and save.</DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="te_first_name">First Name *</Label>
              <Input
                id="te_first_name"
                value={form.first_name}
                onChange={(e) =>
                  setForm({ ...form, first_name: e.target.value })
                }
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="te_last_name">Last Name</Label>
              <Input
                id="te_last_name"
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="te_email">Email</Label>
              <Input
                id="te_email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="te_phone">Phone</Label>
              <Input
                id="te_phone"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="te_qualification">Qualification</Label>
              <Input
                id="te_qualification"
                value={form.qualification}
                onChange={(e) =>
                  setForm({ ...form, qualification: e.target.value })
                }
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="te_years">Years experience</Label>
              <Input
                id="te_years"
                type="number"
                min={0}
                max={60}
                value={form.years_experience}
                onChange={(e) =>
                  setForm({ ...form, years_experience: e.target.value })
                }
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
