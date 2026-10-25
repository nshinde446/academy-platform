"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import apiClient, { apiErrorMessage } from "@/services/api-client";

interface Leave {
  id: string;
  start_date: string;
  end_date: string;
  reason: string | null;
  status: "pending" | "approved" | "rejected";
  decided_at: string | null;
  decision_note: string | null;
}

const STATUS_CHIP: Record<Leave["status"], string> = {
  pending: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  approved: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  rejected: "bg-red-500/15 text-red-700 dark:text-red-300",
};

function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

export default function PortalLeavePage() {
  const router = useRouter();
  const toast = useToast();
  const [leaves, setLeaves] = useState<Leave[]>([]);
  const [loading, setLoading] = useState(true);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [toWithdraw, setToWithdraw] = useState<Leave | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await apiClient.get<Leave[]>("/api/v1/me/leaves");
      setLeaves(r.data);
    } catch (e) {
      if (apiErrorMessage(e, "") === "PASSWORD_CHANGE_REQUIRED") router.push("/change-password");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  async function onApply(e: React.FormEvent) {
    e.preventDefault();
    if (!start || !end) return;
    setSubmitting(true);
    try {
      await apiClient.post("/api/v1/me/leaves", {
        start_date: start,
        end_date: end,
        reason: reason.trim() || null,
      });
      toast.success("Leave request submitted", "Your academic head will review it.");
      setStart("");
      setEnd("");
      setReason("");
      await load();
    } catch (err) {
      toast.error("Could not submit", apiErrorMessage(err, "Check the dates and try again."));
    } finally {
      setSubmitting(false);
    }
  }

  async function confirmWithdraw() {
    if (!toWithdraw) return;
    try {
      await apiClient.delete(`/api/v1/me/leaves/${toWithdraw.id}`);
      toast.success("Request withdrawn");
      await load();
    } catch (err) {
      toast.error("Could not withdraw", apiErrorMessage(err, "Try again."));
    } finally {
      setToWithdraw(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold leading-tight">Leave</h1>
        <p className="text-sm text-muted-foreground">
          Apply for leave and track your requests. A request affects the timetable
          only after your academic head approves it.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,22rem)_1fr]">
        {/* Apply form */}
        <Card>
          <CardContent className="pt-5">
            <form onSubmit={onApply} className="flex flex-col gap-4">
              <h2 className="text-sm font-semibold">Apply for leave</h2>
              <div className="flex flex-col gap-2">
                <Label htmlFor="start">From</Label>
                <Input
                  id="start"
                  type="date"
                  min={todayISO()}
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  required
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="end">To</Label>
                <Input
                  id="end"
                  type="date"
                  min={start || todayISO()}
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                  required
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="reason">Reason (optional)</Label>
                <Input
                  id="reason"
                  type="text"
                  placeholder="e.g. family function"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  maxLength={255}
                />
              </div>
              <Button type="submit" disabled={submitting || !start || !end}>
                {submitting ? "Submitting…" : "Submit request"}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* My requests */}
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold">My requests</h2>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : leaves.length === 0 ? (
            <p className="text-sm text-muted-foreground">No leave requests yet.</p>
          ) : (
            leaves.map((l) => (
              <Card key={l.id}>
                <CardContent className="flex items-start justify-between gap-3 pt-4">
                  <div className="min-w-0">
                    <div className="text-sm font-medium">
                      {l.start_date}
                      {l.end_date !== l.start_date ? ` → ${l.end_date}` : ""}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {l.reason || "No reason given"}
                      {l.decision_note ? ` · note: ${l.decision_note}` : ""}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${STATUS_CHIP[l.status]}`}
                    >
                      {l.status}
                    </span>
                    {l.status === "pending" && (
                      <Button variant="secondary" size="sm" onClick={() => setToWithdraw(l)}>
                        Withdraw
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
        open={!!toWithdraw}
        onOpenChange={(o) => !o && setToWithdraw(null)}
        title="Withdraw this request?"
        description="This cancels your pending leave request. You can submit a new one anytime."
        confirmLabel="Withdraw"
        onConfirm={confirmWithdraw}
      />
    </div>
  );
}
