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
import { useRecordPayment } from "../_hooks/use-fees";
import { PAYMENT_MODES, PAYMENT_MODE_LABELS, inr } from "../_schemas/fees";

const SELECT = "h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export interface PayTarget {
  installmentId: string;
  studentName: string;
  installmentNumber: number;
  balance: number;
}

export function PaymentDialog({
  branchId,
  target,
  onClose,
}: {
  branchId: string | undefined;
  target: PayTarget | null;
  onClose: () => void;
}) {
  return target ? (
    <PaymentForm key={target.installmentId} branchId={branchId} target={target} onClose={onClose} />
  ) : null;
}

function PaymentForm({
  branchId,
  target,
  onClose,
}: {
  branchId: string | undefined;
  target: PayTarget;
  onClose: () => void;
}) {
  const toast = useToast();
  const pay = useRecordPayment(branchId);
  const [amount, setAmount] = useState(String(Math.round(target.balance)));
  const [date, setDate] = useState(today());
  const [mode, setMode] = useState("UPI");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const amt = Number(amount);
    if (!Number.isFinite(amt) || amt <= 0) return setError("Enter a valid amount");
    if (amt > target.balance + 0.01) return setError(`Amount exceeds the balance (${inr(target.balance)})`);
    try {
      await pay.mutateAsync({
        installmentId: target.installmentId,
        body: { amount_paid: amt, payment_date: date, payment_mode: mode, notes: notes.trim() || null },
      });
      toast.success("Payment recorded", `${inr(amt)} · ${PAYMENT_MODE_LABELS[mode]}`);
      onClose();
    } catch (err) {
      const e2 = err as { response?: { data?: { detail?: string; error?: { message?: string } } } };
      setError(e2?.response?.data?.error?.message || e2?.response?.data?.detail || "Failed to record payment");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogPopup>
        <DialogTitle>Record payment</DialogTitle>
        <DialogDescription>
          {target.studentName} · Installment {target.installmentNumber} · balance {inr(target.balance)}
        </DialogDescription>
        <form onSubmit={submit} className="mt-4 flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="pay-amt">Amount paid</Label>
              <Input id="pay-amt" type="number" min={1} value={amount} onChange={(e) => setAmount(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="pay-date">Payment date</Label>
              <Input id="pay-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="pay-mode">Payment mode</Label>
            <select id="pay-mode" className={SELECT} value={mode} onChange={(e) => setMode(e.target.value)}>
              {PAYMENT_MODES.map((m) => (
                <option key={m} value={m}>
                  {PAYMENT_MODE_LABELS[m]}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="pay-notes">Notes (optional)</Label>
            <Input id="pay-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="UPI ref, cheque no…" />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="mt-2 flex justify-end gap-2">
            <DialogClose render={<Button type="button" variant="outline">Cancel</Button>} />
            <Button type="submit" disabled={pay.isPending}>
              {pay.isPending ? "Saving…" : "Save payment"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
