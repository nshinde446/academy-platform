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
import { useDeleteAllStudents } from "../_hooks/use-students";

interface DeleteAllStudentsDialogProps {
  branchId: string;
  /** How many students will be removed — shown in the warning. */
  count: number;
}

const CONFIRM_WORD = "DELETE";

export function DeleteAllStudentsDialog({
  branchId,
  count,
}: DeleteAllStudentsDialogProps) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [done, setDone] = useState<number | null>(null);
  const [error, setError] = useState("");
  const mutation = useDeleteAllStudents(branchId);

  function reset() {
    setTyped("");
    setDone(null);
    setError("");
  }

  async function handleDelete() {
    setError("");
    try {
      const res = await mutation.mutateAsync();
      setDone(res.deleted);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || "Delete failed");
    }
  }

  const armed = typed.trim().toUpperCase() === CONFIRM_WORD;

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
          <Button
            variant="destructive"
            disabled={count === 0}
            onClick={() => setOpen(true)}
          >
            Delete all
          </Button>
        }
      />
      <DialogPopup>
        <DialogTitle>Delete all students</DialogTitle>
        <DialogDescription>
          This soft-deletes <strong>all {count} student(s)</strong> in this
          branch and removes their batch assignments. Batches, courses, and the
          loaded syllabus are kept, so you can re-import a corrected file
          cleanly. Rows are recoverable by an admin, but they disappear from the
          app immediately.
        </DialogDescription>

        <div className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          {done === null ? (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="confirm_delete">
                  Type <span className="font-mono font-semibold">{CONFIRM_WORD}</span>{" "}
                  to confirm
                </Label>
                <Input
                  id="confirm_delete"
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                  autoComplete="off"
                  placeholder={CONFIRM_WORD}
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
                <Button
                  variant="destructive"
                  disabled={!armed || mutation.isPending}
                  onClick={handleDelete}
                >
                  {mutation.isPending
                    ? "Deleting..."
                    : `Delete ${count} student(s)`}
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm">
                Removed {done} student(s). You can now re-import a corrected
                file — the existing batches and syllabus are intact.
              </p>
              <div className="flex justify-end">
                <DialogClose
                  render={<Button type="button">Close</Button>}
                />
              </div>
            </>
          )}
        </div>
      </DialogPopup>
    </Dialog>
  );
}
