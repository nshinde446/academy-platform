"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import apiClient, { apiErrorMessage } from "@/services/api-client";

type Status = "pending" | "approved" | "rejected" | "cancelled";

interface Leave {
  id: string;
  leave_type: string;
  half_day: boolean;
  start_date: string;
  end_date: string;
  days: number | null;
  reason: string | null;
  status: Status;
  applied_on: string | null;
  decided_at: string | null;
  decision_note: string | null;
}

interface TypeBalance {
  leave_type: string;
  quota: number | null;
  used: number;
  pending: number;
  available: number | null;
}

const TYPE_LABEL: Record<string, string> = {
  casual: "Casual",
  sick: "Sick",
  paid: "Paid / Earned",
  lwp: "Leave Without Pay",
};

const STATUS_CHIP: Record<Status, string> = {
  pending: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  approved: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  rejected: "bg-red-500/15 text-red-700 dark:text-red-300",
  cancelled: "bg-muted text-muted-foreground",
};

function ddmmyyyy(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}-${m}-${y}`;
}

function daysBack(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const BACKDATE_DAYS = 7;

export default function PortalLeavePage() {
  const router = useRouter();
  const toast = useToast();
  const now = new Date();

  const [balance, setBalance] = useState<TypeBalance[]>([]);
  const [leaves, setLeaves] = useState<Leave[]>([]);
  const [loading, setLoading] = useState(true);

  // apply form
  const [type, setType] = useState("casual");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [halfDay, setHalfDay] = useState(false);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // filters
  const [fYear, setFYear] = useState(now.getFullYear());
  const [fStatus, setFStatus] = useState("");

  const [toCancel, setToCancel] = useState<Leave | null>(null);
  const [tick, setTick] = useState(0); // bump to refetch after a mutation

  useEffect(() => {
    let on = true;
    (async () => {
      try {
        const [bal, list] = await Promise.all([
          apiClient.get<{ types: TypeBalance[] }>("/api/v1/me/leave-balance", { params: { year: fYear } }),
          apiClient.get<Leave[]>("/api/v1/me/leaves", {
            params: { year: fYear, status: fStatus || undefined },
          }),
        ]);
        if (on) {
          setBalance(bal.data.types);
          setLeaves(list.data);
        }
      } catch (e) {
        if (apiErrorMessage(e, "") === "PASSWORD_CHANGE_REQUIRED") router.push("/change-password");
      } finally {
        if (on) setLoading(false);
      }
    })();
    return () => {
      on = false;
    };
  }, [fYear, fStatus, tick, router]);

  async function onApply(e: React.FormEvent) {
    e.preventDefault();
    if (!start || !end) return;
    setSubmitting(true);
    try {
      await apiClient.post("/api/v1/me/leaves", {
        leave_type: type,
        start_date: start,
        end_date: halfDay ? start : end,
        half_day: halfDay,
        reason: reason.trim() || null,
      });
      toast.success("Leave request submitted", "Your academic head will review it.");
      setStart(""); setEnd(""); setReason(""); setHalfDay(false);
      setTick((t) => t + 1);
    } catch (err) {
      toast.error("Could not submit", apiErrorMessage(err, "Check the dates and try again."));
    } finally {
      setSubmitting(false);
    }
  }

  async function confirmCancel() {
    if (!toCancel) return;
    try {
      await apiClient.delete(`/api/v1/me/leaves/${toCancel.id}`);
      toast.success("Request cancelled");
      setTick((t) => t + 1);
    } catch (err) {
      toast.error("Could not cancel", apiErrorMessage(err, "Try again."));
    } finally {
      setToCancel(null);
    }
  }

  const years = Array.from({ length: 4 }, (_, i) => now.getFullYear() - i);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold leading-tight">Leave</h1>
        <p className="text-sm text-muted-foreground">
          Apply for leave and track your requests. A request affects the timetable
          only after your academic head approves it.
        </p>
      </div>

      {/* Balance cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {balance.map((b) => (
          <Card key={b.leave_type}>
            <CardContent className="pt-4">
              <div className="text-sm font-semibold">{TYPE_LABEL[b.leave_type] ?? b.leave_type}</div>
              {b.quota === null ? (
                <div className="mt-1 text-xs text-muted-foreground">No quota</div>
              ) : (
                <>
                  <div className="mt-1 text-2xl font-bold">{b.available}</div>
                  <div className="text-xs text-muted-foreground">
                    Quota {b.quota} · Used {b.used} · Pending {b.pending}
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,22rem)_1fr]">
        {/* Apply form */}
        <Card>
          <CardContent className="pt-5">
            <form onSubmit={onApply} className="flex flex-col gap-4">
              <h2 className="text-sm font-semibold">Apply for leave</h2>
              <div className="flex flex-col gap-2">
                <Label htmlFor="ltype">Type</Label>
                <select
                  id="ltype"
                  className="h-9 rounded-md border bg-background px-2 text-sm"
                  value={type}
                  onChange={(e) => setType(e.target.value)}
                >
                  {Object.entries(TYPE_LABEL).map(([v, l]) => (
                    <option key={v} value={v}>{l}</option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="start">From</Label>
                <Input id="start" type="date" min={daysBack(BACKDATE_DAYS)}
                  value={start} onChange={(e) => setStart(e.target.value)} required />
              </div>
              {!halfDay && (
                <div className="flex flex-col gap-2">
                  <Label htmlFor="end">To</Label>
                  <Input id="end" type="date" min={start || daysBack(BACKDATE_DAYS)}
                    value={end} onChange={(e) => setEnd(e.target.value)} required />
                </div>
              )}
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={halfDay}
                  onChange={(e) => { setHalfDay(e.target.checked); if (e.target.checked) setEnd(start); }} />
                Half day (0.5)
              </label>
              <div className="flex flex-col gap-2">
                <Label htmlFor="reason">Reason (optional)</Label>
                <Input id="reason" type="text" placeholder="e.g. family function"
                  value={reason} onChange={(e) => setReason(e.target.value)} maxLength={255} />
              </div>
              <p className="text-xs text-muted-foreground">
                Dates use dd-mm-yyyy. Back-dated up to {BACKDATE_DAYS} days. Weekly
                offs and holidays are not counted.
              </p>
              <Button type="submit" disabled={submitting || !start || (!halfDay && !end)}>
                {submitting ? "Submitting…" : "Submit request"}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* My requests */}
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">My requests</h2>
            <div className="flex gap-2">
              <select className="h-8 rounded-md border bg-background px-2 text-xs"
                value={fYear} onChange={(e) => setFYear(Number(e.target.value))}>
                {years.map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
              <select className="h-8 rounded-md border bg-background px-2 text-xs"
                value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
                <option value="">All status</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
          </div>

          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : leaves.length === 0 ? (
            <p className="text-sm text-muted-foreground">No leave requests for this selection.</p>
          ) : (
            leaves.map((l) => (
              <Card key={l.id}>
                <CardContent className="flex items-start justify-between gap-3 pt-4">
                  <div className="min-w-0">
                    <div className="text-sm font-medium">
                      {TYPE_LABEL[l.leave_type] ?? l.leave_type} · {ddmmyyyy(l.start_date)}
                      {l.end_date !== l.start_date ? ` → ${ddmmyyyy(l.end_date)}` : ""}
                      {l.days != null && <span className="ml-1 text-muted-foreground">({l.days}d)</span>}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {l.reason || "No reason given"}
                      {l.decision_note ? ` · note: ${l.decision_note}` : ""}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${STATUS_CHIP[l.status]}`}>
                      {l.status}
                    </span>
                    {l.status === "pending" && (
                      <Button variant="secondary" size="sm" onClick={() => setToCancel(l)}>
                        Cancel
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </div>

      <ConfirmDialog
        open={!!toCancel}
        onOpenChange={(o) => !o && setToCancel(null)}
        title="Cancel this request?"
        description="This cancels your pending leave request. It stays in your history. You can submit a new one anytime."
        confirmLabel="Cancel request"
        onConfirm={confirmCancel}
      />
    </div>
  );
}
