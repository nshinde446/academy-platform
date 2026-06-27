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
import {
  useAddTeacherLeave,
  useDeleteTeacherLeave,
  useTeacherLeaves,
} from "../_hooks/use-lectures";
import type { TeacherSummary } from "../_schemas/lecture";

const SELECT_CLASS =
  "h-9 rounded-lg border border-input bg-background px-2 text-sm";

interface TeacherLeaveDialogProps {
  branchId: string | undefined;
  teachers: TeacherSummary[];
  /** Controlled mode (driven from the page's "Manage" menu). */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** Hide the built-in trigger button when the dialog is opened externally. */
  hideTrigger?: boolean;
}

function fmt(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

export function TeacherLeaveDialog({
  branchId,
  teachers,
  open: openProp,
  onOpenChange,
  hideTrigger,
}: TeacherLeaveDialogProps) {
  const [openInternal, setOpenInternal] = useState(false);
  const open = openProp ?? openInternal;
  const setOpen = (v: boolean) => {
    if (openProp === undefined) setOpenInternal(v);
    onOpenChange?.(v);
  };
  const [teacherId, setTeacherId] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  const leavesQuery = useTeacherLeaves(branchId);
  const addMutation = useAddTeacherLeave(branchId);
  const deleteMutation = useDeleteTeacherLeave(branchId);

  const leaves = leavesQuery.data ?? [];
  const teacherName = (id: string) => {
    const t = teachers.find((x) => x.id === id);
    return t ? `${t.first_name} ${t.last_name}` : "—";
  };

  async function handleAdd() {
    setError("");
    if (!teacherId || !start || !end) {
      setError("Pick a teacher and both dates.");
      return;
    }
    try {
      await addMutation.mutateAsync({
        teacher_id: teacherId,
        start_date: start,
        end_date: end,
        reason: reason.trim() || null,
      });
      setStart("");
      setEnd("");
      setReason("");
    } catch (err: any) {
      setError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          "Could not add leave"
      );
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        setOpen(isOpen);
        if (!isOpen) {
          setError("");
          setTeacherId("");
          setStart("");
          setEnd("");
          setReason("");
        }
      }}
    >
      {!hideTrigger && (
        <DialogTrigger
          render={
            <Button variant="outline" onClick={() => setOpen(true)}>
              Teacher Leave
            </Button>
          }
        />
      )}
      <DialogPopup className="max-w-xl">
        <DialogTitle>Teacher leave</DialogTitle>
        <DialogDescription>
          Planned unavailability. Scheduling rejects a lecture on a teacher&apos;s
          leave day, and the substitute picker hides teachers who are on leave.
        </DialogDescription>

        <div className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lv_teacher">Teacher *</Label>
              <select
                id="lv_teacher"
                value={teacherId}
                onChange={(e) => setTeacherId(e.target.value)}
                className={SELECT_CLASS}
              >
                <option value="">Select…</option>
                {teachers.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.first_name} {t.last_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lv_start">From *</Label>
              <Input
                id="lv_start"
                type="date"
                value={start}
                onChange={(e) => {
                  setStart(e.target.value);
                  if (!end) setEnd(e.target.value);
                }}
                className="w-40"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lv_end">To *</Label>
              <Input
                id="lv_end"
                type="date"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                className="w-40"
              />
            </div>
            <Button
              type="button"
              onClick={handleAdd}
              disabled={addMutation.isPending}
            >
              {addMutation.isPending ? "Adding…" : "Add"}
            </Button>
          </div>

          <Input
            placeholder="Reason (optional)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            aria-label="Leave reason"
          />

          <div className="rounded-xl border ring-1 ring-foreground/10 divide-y divide-border max-h-64 overflow-auto">
            {leavesQuery.isLoading ? (
              <p className="p-3 text-sm text-muted-foreground italic">Loading…</p>
            ) : leaves.length === 0 ? (
              <p className="p-3 text-sm text-muted-foreground italic">
                No leave recorded.
              </p>
            ) : (
              leaves.map((l) => (
                <div
                  key={l.id}
                  className="flex items-center gap-3 px-3 py-2 text-sm"
                >
                  <span className="flex-1 font-medium">
                    {teacherName(l.teacher_id)}
                  </span>
                  <span className="tabular-nums text-muted-foreground">
                    {fmt(l.start_date)} → {fmt(l.end_date)}
                  </span>
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    onClick={() => deleteMutation.mutate(l.id)}
                    disabled={deleteMutation.isPending}
                    aria-label="Remove leave"
                  >
                    Remove
                  </Button>
                </div>
              ))
            )}
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <DialogClose
              render={
                <Button variant="outline" type="button">
                  Close
                </Button>
              }
            />
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
