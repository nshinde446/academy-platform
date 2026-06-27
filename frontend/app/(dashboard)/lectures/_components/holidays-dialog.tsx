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
  useAddHoliday,
  useDeleteHoliday,
  useHolidays,
} from "../_hooks/use-lectures";

interface HolidaysDialogProps {
  branchId: string | undefined;
  /** Controlled mode (driven from the page's "Manage" menu). */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** Hide the built-in trigger button when the dialog is opened externally. */
  hideTrigger?: boolean;
}

function formatDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

export function HolidaysDialog({
  branchId,
  open: openProp,
  onOpenChange,
  hideTrigger,
}: HolidaysDialogProps) {
  const [openInternal, setOpenInternal] = useState(false);
  const open = openProp ?? openInternal;
  const setOpen = (v: boolean) => {
    if (openProp === undefined) setOpenInternal(v);
    onOpenChange?.(v);
  };
  const [date, setDate] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  const holidaysQuery = useHolidays(branchId);
  const addMutation = useAddHoliday(branchId);
  const deleteMutation = useDeleteHoliday(branchId);

  const holidays = holidaysQuery.data ?? [];

  async function handleAdd() {
    setError("");
    if (!date || !name.trim()) {
      setError("Pick a date and enter a name.");
      return;
    }
    try {
      await addMutation.mutateAsync({ date, name: name.trim() });
      setDate("");
      setName("");
    } catch (err: any) {
      setError(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          "Could not add holiday"
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
          setDate("");
          setName("");
        }
      }}
    >
      {!hideTrigger && (
        <DialogTrigger
          render={
            <Button variant="outline" onClick={() => setOpen(true)}>
              Holidays
            </Button>
          }
        />
      )}
      <DialogPopup className="max-w-lg">
        <DialogTitle>Holiday calendar</DialogTitle>
        <DialogDescription>
          Non-teaching days for this branch. The weekly-timetable generator and
          &ldquo;copy to next day&rdquo; both skip these dates.
        </DialogDescription>

        <div className="mt-4 flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="hol_date">Date *</Label>
              <Input
                id="hol_date"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-44"
              />
            </div>
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor="hol_name">Name *</Label>
              <Input
                id="hol_name"
                placeholder="e.g. Diwali"
                value={name}
                onChange={(e) => setName(e.target.value)}
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

          <div className="rounded-xl border ring-1 ring-foreground/10 divide-y divide-border max-h-72 overflow-auto">
            {holidaysQuery.isLoading ? (
              <p className="p-3 text-sm text-muted-foreground italic">Loading…</p>
            ) : holidays.length === 0 ? (
              <p className="p-3 text-sm text-muted-foreground italic">
                No holidays yet.
              </p>
            ) : (
              holidays.map((h) => (
                <div
                  key={h.id}
                  className="flex items-center gap-3 px-3 py-2 text-sm"
                >
                  <span className="w-44 tabular-nums text-muted-foreground">
                    {formatDate(h.holiday_date)}
                  </span>
                  <span className="flex-1 font-medium">{h.name}</span>
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    onClick={() => deleteMutation.mutate(h.id)}
                    disabled={deleteMutation.isPending}
                    aria-label={`Remove holiday ${h.name}`}
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
