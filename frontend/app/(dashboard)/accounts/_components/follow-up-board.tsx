"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useFollowUp } from "../_hooks/use-fees";
import { inr, type FollowUpRow } from "../_schemas/fees";
import { PaymentDialog, type PayTarget } from "./payment-dialog";
import { RemarkDialog, type RemarkTarget } from "./remark-dialog";

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function FollowUpBoard({
  branchId,
  onOpenProfile,
}: {
  branchId: string | undefined;
  onOpenProfile: (studentId: string) => void;
}) {
  const [day, setDay] = useState(todayISO());
  const q = useFollowUp(branchId, day);
  const [pay, setPay] = useState<PayTarget | null>(null);
  const [remark, setRemark] = useState<RemarkTarget | null>(null);

  const data = q.data;

  function markPaid(r: FollowUpRow) {
    setPay({
      installmentId: r.installment_id,
      studentName: r.name,
      installmentNumber: r.installment_number,
      balance: r.amount_due,
    });
  }
  function addRemark(r: FollowUpRow) {
    setRemark({ studentId: r.student_id, profileId: r.profile_id, studentName: r.name, fullyPaid: false });
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="date"
          value={day}
          onChange={(e) => setDay(e.target.value)}
          aria-label="Follow-up day"
          className="h-9 rounded-lg border border-input bg-background px-3 text-sm"
        />
        {data && (
          <div className="grid grid-cols-3 gap-2 sm:flex sm:gap-2">
            <Chip label="Dues" count={data.dues.length} amount={data.dues_total} tone="default" />
            <Chip label="Commitments" count={data.commitments.length} amount={data.commitments_total} tone="warning" />
            <Chip label="Overdue" count={data.overdue.length} amount={data.overdue_total} tone="destructive" />
          </div>
        )}
      </div>

      {!branchId ? (
        <p className="text-muted-foreground text-sm">No branch selected.</p>
      ) : q.isLoading ? (
        <TableSkeleton rows={6} />
      ) : q.isError ? (
        <p className="text-destructive text-sm">Failed to load the follow-up lists.</p>
      ) : !data ? null : (
        <>
          <ListSection
            title="A. Today's Dues"
            rows={data.dues}
            onName={onOpenProfile}
            onPay={markPaid}
            onRemark={addRemark}
            empty="No installments due on this day."
          />
          <ListSection
            title="B. Today's Commitments"
            rows={data.commitments}
            onName={onOpenProfile}
            onPay={markPaid}
            onRemark={addRemark}
            empty="No one promised to pay on this day."
          />
          <ListSection
            title="C. Overdue (oldest first)"
            rows={data.overdue}
            onName={onOpenProfile}
            onPay={markPaid}
            onRemark={addRemark}
            showOverdue
            empty="Nothing overdue — nice."
          />
        </>
      )}

      <PaymentDialog branchId={branchId} target={pay} onClose={() => setPay(null)} />
      <RemarkDialog branchId={branchId} target={remark} onClose={() => setRemark(null)} />
    </div>
  );
}

function Chip({
  label,
  count,
  amount,
  tone,
}: {
  label: string;
  count: number;
  amount: number;
  tone: "default" | "warning" | "destructive";
}) {
  const ring =
    tone === "destructive"
      ? "ring-destructive/30"
      : tone === "warning"
        ? "ring-amber-400/40"
        : "ring-foreground/10";
  return (
    <div className={`rounded-lg border bg-card px-3 py-1.5 ring-1 ${ring}`}>
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="text-sm font-semibold tabular-nums">
        {count} · {inr(amount)}
      </div>
    </div>
  );
}

function ListSection({
  title,
  rows,
  onName,
  onPay,
  onRemark,
  showOverdue = false,
  empty,
}: {
  title: string;
  rows: FollowUpRow[];
  onName: (studentId: string) => void;
  onPay: (r: FollowUpRow) => void;
  onRemark: (r: FollowUpRow) => void;
  showOverdue?: boolean;
  empty: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {rows.length === 0 ? (
        <Card size="sm">
          <CardContent>
            <p className="text-sm text-muted-foreground">{empty}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Student</TableHead>
                <TableHead className="hidden sm:table-cell">PRN</TableHead>
                <TableHead className="hidden md:table-cell">Batch</TableHead>
                {showOverdue && <TableHead className="hidden lg:table-cell">Due</TableHead>}
                <TableHead className="text-right">Amount</TableHead>
                {showOverdue && <TableHead className="text-right hidden sm:table-cell">Days</TableHead>}
                <TableHead className="hidden lg:table-cell">Phone</TableHead>
                <TableHead className="hidden xl:table-cell">Last remark</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.installment_id}>
                  <TableCell>
                    <button
                      type="button"
                      onClick={() => onName(r.student_id)}
                      className="font-medium text-foreground hover:underline"
                    >
                      {r.name}
                    </button>
                  </TableCell>
                  <TableCell className="hidden sm:table-cell font-mono text-xs text-muted-foreground">
                    {r.prn || "—"}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-muted-foreground">{r.batch || "—"}</TableCell>
                  {showOverdue && (
                    <TableCell className="hidden lg:table-cell tabular-nums text-sm text-muted-foreground">
                      {r.due_date}
                    </TableCell>
                  )}
                  <TableCell className="text-right tabular-nums font-medium">{inr(r.amount_due)}</TableCell>
                  {showOverdue && (
                    <TableCell className="text-right hidden sm:table-cell tabular-nums text-destructive">
                      {r.days_overdue}
                    </TableCell>
                  )}
                  <TableCell className="hidden lg:table-cell tabular-nums text-sm text-muted-foreground">
                    {r.phone || "—"}
                  </TableCell>
                  <TableCell className="hidden xl:table-cell max-w-[220px] truncate text-sm text-muted-foreground">
                    {r.last_remark ? (
                      <span title={r.last_remark}>
                        {r.last_remark_date ? `${r.last_remark_date}: ` : ""}
                        {r.last_remark}
                      </span>
                    ) : (
                      <span className="italic">No remark yet</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1.5">
                      <Button size="xs" onClick={() => onPay(r)}>
                        Mark paid
                      </Button>
                      <Button size="xs" variant="outline" onClick={() => onRemark(r)}>
                        Remark
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
