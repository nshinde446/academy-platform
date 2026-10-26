"use client";

import { use } from "react";
import Link from "next/link";
import { useBranchId } from "@/store/user-store";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { downloadPayroll, useLedger, type LedgerRow } from "@/hooks/use-payroll";

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function num(v: number): string {
  return v === Math.trunc(v) ? String(v) : v.toFixed(1);
}

const ENTRY_LABEL: Record<string, string> = {
  extra_added: "Extra added",
  compensation_used: "Compensation used",
  cap_trim: "Cap trim",
  makeup_credit: "Make-up credit",
  reversal: "Reversal",
  manual_adjustment: "Manual adjustment",
};

function fmtWhen(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString();
}

export default function StaffLedgerPage({
  params,
}: {
  params: Promise<{ staffId: string }>;
}) {
  const { staffId } = use(params);
  const { branchId } = useBranchId();
  const ledger = useLedger(branchId, staffId);
  const data = ledger.data;

  async function exportAs(fmt: "pdf" | "xlsx") {
    if (!branchId) return;
    await downloadPayroll(`/api/v1/payroll/staff/${staffId}/ledger/export`, {
      branch_id: branchId,
      fmt,
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={data ? `${data.name} — Ledger` : "Carry-Forward Ledger"}
        description="Every carry-forward balance movement for this staff member, in order. The ledger is append-only — a correction is a new reversal row, never an edit."
        actions={
          <>
            <Button variant="outline" render={<Link href="/payroll" />}>
              Back to report
            </Button>
            <Button variant="outline" disabled={!data?.rows.length} onClick={() => exportAs("xlsx")}>
              Excel
            </Button>
            <Button variant="outline" disabled={!data?.rows.length} onClick={() => exportAs("pdf")}>
              PDF
            </Button>
          </>
        }
      >
        {data && (
          <div className="flex items-center gap-2 text-sm">
            <span className="font-mono text-xs text-muted-foreground">{data.emp_code}</span>
            <Badge variant="default">Current balance: {num(data.current_balance)}</Badge>
          </div>
        )}
      </PageHeader>

      {ledger.isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      ) : ledger.isError ? (
        <ErrorState onRetry={() => ledger.refetch()} />
      ) : !data || data.rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No ledger entries yet.</p>
      ) : (
        <Table containerClassName="rounded-md border">
          <TableHeader>
            <TableRow>
              <TableHead>Month</TableHead>
              <TableHead>Entry</TableHead>
              <TableHead className="text-right">Days</TableHead>
              <TableHead className="text-right">Balance</TableHead>
              <TableHead>By</TableHead>
              <TableHead>When</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.rows.map((r: LedgerRow) => (
              <TableRow key={r.seq}>
                <TableCell>{MONTHS[r.month - 1]} {r.year}</TableCell>
                <TableCell>{ENTRY_LABEL[r.entry_type] ?? r.entry_type}</TableCell>
                <TableCell className="text-right">{`${r.days > 0 ? "+" : ""}${num(r.days)}`}</TableCell>
                <TableCell className="text-right font-medium">{num(r.running_balance)}</TableCell>
                <TableCell className="text-muted-foreground">{r.created_by ?? "—"}</TableCell>
                <TableCell className="text-muted-foreground">{fmtWhen(r.created_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
