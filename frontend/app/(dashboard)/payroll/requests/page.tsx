"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useBranchId } from "@/store/user-store";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogPopup, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { PromptDialog } from "@/components/ui/prompt-dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { apiErrorMessage } from "@/lib/api-error";
import {
  useDecideRequest,
  usePayrollStaff,
  useRaiseRequest,
  useRequestHistory,
  useRequests,
  type ExtraDayRequestDto,
} from "@/hooks/use-payroll";

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const TABS: { label: string; status: string }[] = [
  { label: "Pending", status: "PENDING" },
  { label: "Approved", status: "APPROVED" },
  { label: "Rejected", status: "REJECTED" },
  { label: "All", status: "" },
];

const STATUS_TONE: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  PENDING: "secondary",
  APPROVED: "default",
  REJECTED: "destructive",
  CANCELLED: "outline",
  EXPIRED: "outline",
};

function ym(y: number, m: number): string {
  return `${MONTHS[m - 1]} ${y}`;
}

export default function PayrollRequestsPage() {
  const { branchId } = useBranchId();
  const toast = useToast();
  const [tab, setTab] = useState("PENDING");
  const requests = useRequests(branchId, tab || undefined);
  const decide = useDecideRequest(branchId);

  const staffQuery = usePayrollStaff(branchId);
  const staffName = useMemo(() => {
    const map = new Map<string, string>();
    (staffQuery.data ?? []).forEach((s) => map.set(s.id, `${s.first_name} ${s.last_name}`.trim()));
    return map;
  }, [staffQuery.data]);

  const [historyFor, setHistoryFor] = useState<ExtraDayRequestDto | null>(null);
  const [raiseOpen, setRaiseOpen] = useState(false);
  const [rejectFor, setRejectFor] = useState<ExtraDayRequestDto | null>(null);

  async function act(req: ExtraDayRequestDto, verb: "approve" | "cancel", note?: string) {
    try {
      await decide.mutateAsync({ id: req.id, verb, note });
      toast.success(`Request ${verb === "cancel" ? "cancelled" : verb + "d"}`);
    } catch (e) {
      toast.error(`Could not ${verb}`, apiErrorMessage(e, "Please try again."));
    }
  }

  async function rejectWithReason(req: ExtraDayRequestDto, note: string) {
    try {
      await decide.mutateAsync({ id: req.id, verb: "reject", note: note || undefined });
      toast.success("Request rejected");
    } catch (e) {
      toast.error("Could not reject", apiErrorMessage(e, "Please try again."));
    }
  }

  const rows = requests.data ?? [];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Extra-Day Requests"
        description="When a month closes with an uncovered shortfall, a request can be raised to make up the days next month. The Super Admin approves or rejects; an approved request defers the shortfall (not unpaid) and raises next month's required days."
        actions={
          <>
            <Button variant="outline" render={<Link href="/payroll" />}>Report</Button>
            <Button onClick={() => setRaiseOpen(true)}>Raise request</Button>
          </>
        }
      >
        <div className="flex flex-wrap gap-1">
          {TABS.map((t) => (
            <button
              key={t.label}
              onClick={() => setTab(t.status)}
              className={`rounded-md px-3 py-1 text-sm transition-colors ${
                tab === t.status ? "bg-muted font-medium" : "text-muted-foreground hover:bg-muted"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </PageHeader>

      {requests.isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      ) : requests.isError ? (
        <ErrorState onRetry={() => requests.refetch()} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No requests in this tab.</p>
      ) : (
        <Table containerClassName="rounded-md border">
          <TableHeader>
            <TableRow>
              <TableHead>Staff</TableHead>
              <TableHead>Shortfall month</TableHead>
              <TableHead>Make-up month</TableHead>
              <TableHead className="text-right">Days</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id}>
                <TableCell>{staffName.get(r.staff_id) ?? r.staff_id.slice(0, 8)}</TableCell>
                <TableCell>{ym(r.source_year, r.source_month)}</TableCell>
                <TableCell>{ym(r.target_year, r.target_month)}</TableCell>
                <TableCell className="text-right">{r.shortfall_days}</TableCell>
                <TableCell>
                  <Badge variant={STATUS_TONE[r.request_status] ?? "outline"}>{r.request_status}</Badge>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    {r.request_status === "PENDING" && (
                      <>
                        <Button size="sm" variant="outline" onClick={() => act(r, "approve")}>Approve</Button>
                        <Button size="sm" variant="outline" onClick={() => setRejectFor(r)}>Reject</Button>
                        <Button size="sm" variant="ghost" onClick={() => act(r, "cancel")}>Cancel</Button>
                      </>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => setHistoryFor(r)}>History</Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <HistoryDialog
        branchId={branchId}
        request={historyFor}
        onClose={() => setHistoryFor(null)}
      />
      <RaiseDialog
        open={raiseOpen}
        onClose={() => setRaiseOpen(false)}
        branchId={branchId}
      />
      <PromptDialog
        open={rejectFor !== null}
        onOpenChange={(o) => !o && setRejectFor(null)}
        title="Reject request"
        description="Optionally note why. The shortfall stays unpaid."
        label="Reason (optional)"
        confirmLabel="Reject"
        onConfirm={async (note) => {
          if (rejectFor) await rejectWithReason(rejectFor, note);
          setRejectFor(null);
        }}
      />
    </div>
  );
}

function HistoryDialog({
  branchId,
  request,
  onClose,
}: {
  branchId: string | undefined;
  request: ExtraDayRequestDto | null;
  onClose: () => void;
}) {
  const history = useRequestHistory(branchId, request?.id);
  return (
    <Dialog open={!!request} onOpenChange={(o) => !o && onClose()}>
      <DialogPopup>
        <DialogTitle>Request history</DialogTitle>
        <DialogDescription className="sr-only">
          Status changes for this extra-day request.
        </DialogDescription>
        {history.isLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : (
          <ol className="flex flex-col gap-2 text-sm">
            {(history.data ?? []).map((h, i) => (
              <li key={i} className="flex items-center justify-between gap-3">
                <span>
                  <span className="font-medium">{h.to_status}</span>
                  {h.note && <span className="ml-2 text-muted-foreground">— {h.note}</span>}
                </span>
                <span className="text-xs text-muted-foreground">
                  {h.changed_at ? new Date(h.changed_at).toLocaleString() : ""}
                </span>
              </li>
            ))}
          </ol>
        )}
      </DialogPopup>
    </Dialog>
  );
}

function RaiseDialog({
  open,
  onClose,
  branchId,
}: {
  open: boolean;
  onClose: () => void;
  branchId: string | undefined;
}) {
  const toast = useToast();
  const staff = usePayrollStaff(branchId).data ?? [];
  const raise = useRaiseRequest(branchId);
  const now = new Date();
  const [staffId, setStaffId] = useState("");
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [days, setDays] = useState("1");

  async function submit() {
    if (!staffId) return toast.error("Pick a staff member");
    try {
      await raise.mutateAsync({
        staff_id: staffId, source_year: year, source_month: month,
        shortfall_days: Number(days),
      });
      toast.success("Request raised");
      onClose();
    } catch (e) {
      toast.error("Could not raise", apiErrorMessage(e, "There may be no uncovered shortfall for that month."));
    }
  }

  const years = Array.from({ length: 6 }, (_, i) => now.getFullYear() - i);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogPopup>
        <DialogTitle>Raise extra-day request</DialogTitle>
        <DialogDescription className="sr-only">
          Raise a request to make up an uncovered shortfall next month.
        </DialogDescription>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="r-staff">Staff</Label>
            <select
              id="r-staff"
              className="h-9 rounded-md border bg-background px-2 text-sm"
              value={staffId}
              onChange={(e) => setStaffId(e.target.value)}
            >
              <option value="">Select…</option>
              {staff.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.emp_code} — {s.first_name} {s.last_name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex gap-2">
            <div className="flex flex-col gap-1">
              <Label htmlFor="r-month">Shortfall month</Label>
              <select
                id="r-month"
                className="h-9 rounded-md border bg-background px-2 text-sm"
                value={month}
                onChange={(e) => setMonth(Number(e.target.value))}
              >
                {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="r-year">Year</Label>
              <select
                id="r-year"
                className="h-9 rounded-md border bg-background px-2 text-sm"
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
              >
                {years.map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="r-days">Days</Label>
              <Input id="r-days" type="number" step="0.5" min="0.5" value={days}
                onChange={(e) => setDays(e.target.value)} className="w-20" />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={submit} disabled={raise.isPending}>Raise</Button>
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
