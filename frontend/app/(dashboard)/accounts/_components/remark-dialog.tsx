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
import { useAddRemark } from "../_hooks/use-fees";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export interface RemarkTarget {
  studentId: string;
  profileId: string;
  studentName: string;
  fullyPaid: boolean;
}

export function RemarkDialog({
  branchId,
  target,
  onClose,
}: {
  branchId: string | undefined;
  target: RemarkTarget | null;
  onClose: () => void;
}) {
  return target ? (
    <RemarkForm key={target.studentId} branchId={branchId} target={target} onClose={onClose} />
  ) : null;
}

function RemarkForm({
  branchId,
  target,
  onClose,
}: {
  branchId: string | undefined;
  target: RemarkTarget;
  onClose: () => void;
}) {
  const toast = useToast();
  const add = useAddRemark(branchId);
  const [text, setText] = useState("");
  const [followup, setFollowup] = useState("");
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return setError("Enter what was discussed");
    if (!followup && !target.fullyPaid) return setError("A next follow-up date is required until the fee is fully paid");
    try {
      await add.mutateAsync({
        student_id: target.studentId,
        profile_id: target.profileId,
        remark_text: text.trim(),
        call_date: today(),
        next_followup_date: followup || null,
      });
      toast.success("Remark saved", followup ? `Follow up on ${followup}` : "No follow-up (fully paid)");
      onClose();
    } catch (err) {
      const e2 = err as { response?: { data?: { detail?: string; error?: { message?: string } } } };
      setError(e2?.response?.data?.error?.message || e2?.response?.data?.detail || "Failed to save remark");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogPopup>
        <DialogTitle>Add remark</DialogTitle>
        <DialogDescription>{target.studentName} — log the call and the next follow-up date.</DialogDescription>
        <form onSubmit={submit} className="mt-4 flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="rem-text">What was discussed</Label>
            <Input id="rem-text" value={text} onChange={(e) => setText(e.target.value)} placeholder="Parent will pay on 15th…" />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="rem-followup">
              Next follow-up date{target.fullyPaid ? " (optional — fully paid)" : ""}
            </Label>
            <Input id="rem-followup" type="date" value={followup} onChange={(e) => setFollowup(e.target.value)} />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="mt-2 flex justify-end gap-2">
            <DialogClose render={<Button type="button" variant="outline">Cancel</Button>} />
            <Button type="submit" disabled={add.isPending}>
              {add.isPending ? "Saving…" : "Save remark"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
