"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useFeeProfile } from "../_hooks/use-fees";
import { inr, type Installment } from "../_schemas/fees";
import { PaymentDialog, type PayTarget } from "./payment-dialog";
import { RemarkDialog, type RemarkTarget } from "./remark-dialog";

function statusBadge(s: Installment["installment_status"]) {
  if (s === "PAID") return <Badge variant="success">Paid</Badge>;
  if (s === "PARTIAL") return <Badge variant="warning">Partial</Badge>;
  if (s === "OVERDUE") return <Badge variant="destructive">Overdue</Badge>;
  return <Badge variant="secondary">Pending</Badge>;
}

export function FeeProfileDialog({
  branchId,
  studentId,
  onClose,
}: {
  branchId: string | undefined;
  studentId: string | null;
  onClose: () => void;
}) {
  const q = useFeeProfile(branchId, studentId ?? undefined);
  const [pay, setPay] = useState<PayTarget | null>(null);
  const [remark, setRemark] = useState<RemarkTarget | null>(null);
  const p = q.data;

  return (
    <Dialog open={studentId !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogPopup className="max-w-3xl">
        <DialogTitle>Student fee profile</DialogTitle>
        <DialogDescription>
          Fee summary, installment schedule and call history.
        </DialogDescription>

        {q.isLoading ? (
          <div className="mt-4">
            <TableSkeleton rows={5} />
          </div>
        ) : q.isError || !p ? (
          <p className="mt-4 text-sm text-muted-foreground">
            No fee profile for this student yet.
          </p>
        ) : (
          <div className="mt-4 flex max-h-[70vh] flex-col gap-5 overflow-y-auto pr-1">
            {/* Summary */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Kpi label="Agreed fee" value={inr(p.agreed_fee)} />
              <Kpi label="Discount" value={inr(p.discount_amount)} />
              <Kpi label="Paid" value={inr(p.total_paid)} tone="success" />
              <Kpi label="Pending" value={inr(p.total_pending)} tone={p.total_pending > 0 ? "destructive" : "default"} />
            </div>
            <p className="text-xs text-muted-foreground">
              {p.payment_mode === "ONE_TIME" ? "One-time payment" : `Installment plan (${p.installments.length})`} ·
              admitted {p.admission_date} · actual fee {inr(p.actual_fee)}
            </p>

            {/* Installments */}
            <div className="rounded-lg border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10 text-right">#</TableHead>
                    <TableHead>Due</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="text-right hidden sm:table-cell">Paid</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {p.installments.map((i) => {
                    const balance = Math.round((i.amount - i.paid_amount) * 100) / 100;
                    const payable = i.installment_status !== "PAID" && balance > 0;
                    return (
                      <TableRow key={i.id}>
                        <TableCell className="text-right tabular-nums text-muted-foreground">
                          {i.installment_number}
                        </TableCell>
                        <TableCell className="tabular-nums text-sm">{i.due_date}</TableCell>
                        <TableCell className="text-right tabular-nums">{inr(i.amount)}</TableCell>
                        <TableCell className="text-right tabular-nums hidden sm:table-cell text-muted-foreground">
                          {i.paid_amount ? inr(i.paid_amount) : "—"}
                        </TableCell>
                        <TableCell>{statusBadge(i.installment_status)}</TableCell>
                        <TableCell className="text-right">
                          {payable && (
                            <Button
                              size="xs"
                              onClick={() =>
                                setPay({
                                  installmentId: i.id,
                                  studentName: "This student",
                                  installmentNumber: i.installment_number,
                                  balance,
                                })
                              }
                            >
                              Pay
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>

            {/* Call log */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold">Call log</h4>
                <Button
                  size="xs"
                  variant="outline"
                  onClick={() =>
                    setRemark({
                      studentId: p.student_id,
                      profileId: p.id,
                      studentName: "This student",
                      fullyPaid: p.total_pending <= 0,
                    })
                  }
                >
                  Add remark
                </Button>
              </div>
              {p.remarks.length === 0 ? (
                <p className="text-sm text-muted-foreground">No calls logged yet.</p>
              ) : (
                <ul className="flex flex-col divide-y rounded-lg border">
                  {p.remarks.map((r) => (
                    <li key={r.id} className="flex flex-col gap-0.5 px-3 py-2 text-sm">
                      <span>{r.remark_text}</span>
                      <span className="text-xs text-muted-foreground">
                        {r.call_date}
                        {r.next_followup_date ? ` · follow up ${r.next_followup_date}` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        <PaymentDialog branchId={branchId} target={pay} onClose={() => setPay(null)} />
        <RemarkDialog branchId={branchId} target={remark} onClose={() => setRemark(null)} />
      </DialogPopup>
    </Dialog>
  );
}

function Kpi({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "success" | "destructive" }) {
  const cls =
    tone === "destructive" ? "text-destructive" : tone === "success" ? "text-emerald-600 dark:text-emerald-400" : "text-foreground";
  return (
    <div className="flex flex-col gap-0.5 rounded-lg border bg-card px-3 py-2">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`text-base font-semibold tabular-nums ${cls}`}>{value}</span>
    </div>
  );
}
