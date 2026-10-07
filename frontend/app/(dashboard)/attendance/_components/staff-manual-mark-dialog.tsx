"use client";

import { useState } from "react";
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
import { useToast } from "@/components/ui/toast";
import { useStaffManualMark } from "../_hooks/use-staff-attendance";
import type { StaffDayRegisterRow } from "../_schemas/staff-attendance";

interface Props {
  branchId: string | undefined;
  day: string;
  staff: StaffDayRegisterRow; // the row being marked
  onClose: () => void;
}

// Manager hand-enters a staff In Time (and optionally Out Time) when the device
// missed the punch (PDF3). The backend tags the row "Manually Marked by:
// Name (Role)" from the logged-in user — the name is never typed here.
//
// Mount this with a `key` of the staff id so each open starts seeded from that
// staff's current times.
export function StaffManualMarkDialog({ branchId, day, staff, onClose }: Props) {
  const [inTime, setInTime] = useState(staff.in_time?.slice(0, 5) ?? "");
  const [outTime, setOutTime] = useState(staff.out_time?.slice(0, 5) ?? "");
  const [error, setError] = useState("");
  const toast = useToast();
  const mutation = useStaffManualMark(branchId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!inTime) {
      setError("In Time is required.");
      return;
    }
    if (outTime && outTime <= inTime) {
      setError("Out Time must be after In Time.");
      return;
    }
    try {
      await mutation.mutateAsync({
        staff_id: staff.staff_id,
        day,
        in_time: inTime,
        out_time: outTime || null,
      });
      toast.success(`Attendance marked for ${staff.name}.`);
      onClose();
    } catch (err) {
      const message =
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message ?? "Failed to mark attendance.";
      setError(message);
    }
  }

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogPopup>
        <DialogTitle>Mark attendance manually</DialogTitle>
        <DialogDescription>
          {`Enter ${staff.name}'s In Time (and Out Time, if known) for this day. It is recorded as a manual entry tagged with your name.`}
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="sm-in">In Time</Label>
              <Input
                id="sm-in"
                type="time"
                step={60}
                required
                value={inTime}
                onChange={(e) => setInTime(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="sm-out">Out Time (optional)</Label>
              <Input
                id="sm-out"
                type="time"
                step={60}
                value={outTime}
                onChange={(e) => setOutTime(e.target.value)}
              />
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="mt-2 flex justify-end gap-2">
            <DialogClose
              render={
                <Button type="button" variant="outline">
                  Cancel
                </Button>
              }
            />
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save entry"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
