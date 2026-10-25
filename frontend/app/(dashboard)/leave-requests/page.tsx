"use client";

import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import apiClient, { apiErrorMessage } from "@/services/api-client";
import { useBranchId } from "@/store/user-store";

interface LeaveRequest {
  id: string;
  teacher_id: string;
  teacher_name: string;
  start_date: string;
  end_date: string;
  reason: string | null;
  status: "pending" | "approved" | "rejected";
  decided_at: string | null;
  decision_note: string | null;
}

const STATUS_CHIP: Record<LeaveRequest["status"], string> = {
  pending: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  approved: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  rejected: "bg-red-500/15 text-red-700 dark:text-red-300",
};

const FILTERS = ["pending", "approved", "rejected", "all"] as const;
type Filter = (typeof FILTERS)[number];

export default function LeaveRequestsPage() {
  const { branchId } = useBranchId();
  const toast = useToast();
  const [rows, setRows] = useState<LeaveRequest[]>([]);
  const [filter, setFilter] = useState<Filter>("pending");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!branchId) return;
    setLoading(true);
    try {
      const r = await apiClient.get<LeaveRequest[]>("/api/v1/admin/leave-requests", {
        params: { branch_id: branchId, status: filter === "all" ? undefined : filter },
      });
      setRows(r.data);
    } catch (e) {
      toast.error("Could not load requests", apiErrorMessage(e, "Try again."));
    } finally {
      setLoading(false);
    }
  }, [branchId, filter, toast]);

  useEffect(() => {
    // load() sets state only after an await (not synchronously).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  async function decide(id: string, action: "approve" | "reject") {
    if (!branchId) return;
    setBusyId(id);
    try {
      await apiClient.post(`/api/v1/admin/leave-requests/${id}/${action}`, null, {
        params: { branch_id: branchId },
      });
      toast.success(action === "approve" ? "Leave approved" : "Leave rejected");
      await load();
    } catch (e) {
      toast.error("Action failed", apiErrorMessage(e, "Try again."));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="Leave Requests" />

      <div className="flex gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-md border px-3 py-1 text-[13px] capitalize transition-colors ${
              filter === f
                ? "border-primary bg-primary/10 font-medium text-foreground"
                : "border-border text-muted-foreground hover:bg-muted"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No {filter === "all" ? "" : filter} requests.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {rows.map((l) => (
            <Card key={l.id}>
              <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-4">
                <div className="min-w-0">
                  <div className="text-sm font-medium">{l.teacher_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {l.start_date}
                    {l.end_date !== l.start_date ? ` → ${l.end_date}` : ""}
                    {l.reason ? ` · ${l.reason}` : ""}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${STATUS_CHIP[l.status]}`}
                  >
                    {l.status}
                  </span>
                  {l.status === "pending" && (
                    <>
                      <Button
                        size="sm"
                        disabled={busyId === l.id}
                        onClick={() => decide(l.id, "approve")}
                      >
                        Approve
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={busyId === l.id}
                        onClick={() => decide(l.id, "reject")}
                      >
                        Reject
                      </Button>
                    </>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
