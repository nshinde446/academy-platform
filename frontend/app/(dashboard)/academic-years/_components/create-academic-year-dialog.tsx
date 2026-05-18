"use client";

import { useEffect, useState } from "react";
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
import type { AcademicYearCreate } from "../_schemas/academic-year";

interface CreateAcademicYearDialogProps {
  onSubmit: (
    data: Omit<AcademicYearCreate, "branch_id">
  ) => Promise<void> | void;
  isPending: boolean;
}

export function CreateAcademicYearDialog({
  onSubmit,
  isPending,
}: CreateAcademicYearDialogProps) {
  const [open, setOpen] = useState(false);
  const [startYear, setStartYear] = useState("");
  const [error, setError] = useState("");

  // Derive end year and name from start year
  const startInt = parseInt(startYear, 10);
  const valid = Number.isFinite(startInt) && startInt > 1900 && startInt < 3000;
  const endInt = valid ? startInt + 1 : null;
  const name = valid ? `${startInt}-${endInt}` : "";

  useEffect(() => {
    if (!open) {
      setStartYear("");
      setError("");
    }
  }, [open]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid || endInt === null) {
      setError("Enter a valid start year (e.g., 2025)");
      return;
    }
    try {
      await onSubmit({
        name,
        start_year: startInt,
        end_year: endInt,
      });
      setOpen(false);
    } catch (err: any) {
      setError(
        err.response?.data?.error?.message || "Failed to create academic year"
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button onClick={() => setOpen(true)}>Create Academic Year</Button>
        }
      />
      <DialogPopup>
        <DialogTitle>Create Academic Year</DialogTitle>
        <DialogDescription>
          Define an academic year for this branch. The end year and name are
          derived from the start year.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ay_start_year">Start Year *</Label>
              <Input
                id="ay_start_year"
                type="number"
                min={1900}
                max={3000}
                value={startYear}
                onChange={(e) => setStartYear(e.target.value)}
                placeholder="2025"
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ay_name">Name</Label>
              <Input
                id="ay_name"
                value={name}
                readOnly
                className="bg-muted"
                placeholder="—"
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
            <Button type="submit" disabled={isPending || !valid}>
              {isPending ? "Creating..." : "Create"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
