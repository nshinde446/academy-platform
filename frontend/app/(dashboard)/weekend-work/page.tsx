"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { InfoHint } from "@/components/ui/info-hint";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import apiClient, { apiErrorMessage } from "@/services/api-client";
import { useBranchId } from "@/store/user-store";

interface WeekendRow {
  id: string;
  staff_id: string;
  emp_code: string | null;
  name: string;
  work_date: string;
  day_code: string;
  time_in: string | null;
  time_out: string | null;
  work_minutes: number;
  work_content: string | null;
  approval_status: string;
  approval_note: string | null;
  marked_absent: boolean;
  credit_days: number;
  warning: boolean;
}

interface Staff {
  id: string;
  emp_code: string;
  first_name: string;
  last_name: string;
}

const STATUS_CHIP: Record<string, string> = {
  PENDING: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  APPROVED: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  REJECTED: "bg-red-500/15 text-red-700 dark:text-red-300",
};

const STATUS_FILTERS = ["", "PENDING", "APPROVED", "REJECTED"] as const;

function monthRange(): { from: string; to: string } {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  const last = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return { from: iso(first), to: iso(last) };
}

function hhmm(minutes: number): string {
  const h = Math.floor((minutes || 0) / 60);
  return `${h}:${String((minutes || 0) % 60).padStart(2, "0")}`;
}

function isWeekend(iso: string): boolean {
  if (!iso) return false;
  const d = new Date(iso + "T00:00:00");
  return d.getDay() === 0 || d.getDay() === 6; // Sun | Sat
}

async function downloadFile(path: string, params: URLSearchParams) {
  const res = await apiClient.get(`${path}?${params.toString()}`, { responseType: "blob" });
  const disposition = res.headers["content-disposition"] as string | undefined;
  const filename = disposition?.match(/filename="?([^"]+)"?/)?.[1] ?? "weekend-work.xlsx";
  const url = window.URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export default function WeekendWorkPage() {
  const { branchId } = useBranchId();
  const toast = useToast();
  const range = useMemo(() => monthRange(), []);

  const [from, setFrom] = useState(range.from);
  const [to, setTo] = useState(range.to);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [staffFilter, setStaffFilter] = useState<string>("");

  const [rows, setRows] = useState<WeekendRow[]>([]);
  const [rules, setRules] = useState<string[]>([]);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  // Pre-approval form.
  const [paDate, setPaDate] = useState("");
  const [paStaff, setPaStaff] = useState<Set<string>>(new Set());
  const [paBusy, setPaBusy] = useState(false);

  const load = useCallback(async () => {
    if (!branchId) return;
    setLoading(true);
    try {
      const res = await apiClient.get<{ rows: WeekendRow[]; rules: string[] }>(
        "/api/v1/admin/weekend-work",
        {
          params: {
            branch_id: branchId,
            from,
            to,
            status: statusFilter || undefined,
            staff_id: staffFilter || undefined,
          },
        },
      );
      setRows(res.data.rows);
      setRules(res.data.rules);
    } catch (e) {
      toast.error("Could not load the report", apiErrorMessage(e, "Try again."));
    } finally {
      setLoading(false);
    }
  }, [branchId, from, to, statusFilter, staffFilter, toast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  useEffect(() => {
    if (!branchId) return;
    apiClient
      .get<Staff[]>("/api/v1/staff", { params: { branch_id: branchId } })
      .then((r) => setStaff(r.data))
      .catch(() => setStaff([]));
  }, [branchId]);

  async function act(path: string, body: unknown, ok: string) {
    if (!branchId) return;
    setBusyId(path);
    try {
      await apiClient.post(path, body, { params: { branch_id: branchId } });
      toast.success(ok);
      await load();
    } catch (e) {
      toast.error("Action failed", apiErrorMessage(e, "Try again."));
    } finally {
      setBusyId(null);
    }
  }

  async function preapprove() {
    if (!branchId || !paDate || paStaff.size === 0) return;
    if (!isWeekend(paDate)) {
      toast.error("Pick a weekend", "Pre-approval is only for Saturdays and Sundays.");
      return;
    }
    setPaBusy(true);
    try {
      const res = await apiClient.post<{ created: number; skipped: number }>(
        "/api/v1/admin/weekend-work/preapprove",
        { work_date: paDate, staff_ids: [...paStaff] },
        { params: { branch_id: branchId } },
      );
      toast.success(
        "Pre-approved",
        `${res.data.created} added · ${res.data.skipped} already present`,
      );
      setPaStaff(new Set());
      await load();
    } catch (e) {
      toast.error("Could not pre-approve", apiErrorMessage(e, "Try again."));
    } finally {
      setPaBusy(false);
    }
  }

  async function exportXlsx() {
    if (!branchId) return;
    const params = new URLSearchParams({ branch_id: branchId, from, to });
    if (statusFilter) params.append("status", statusFilter);
    if (staffFilter) params.append("staff_id", staffFilter);
    try {
      await downloadFile("/api/v1/admin/weekend-work/export", params);
    } catch {
      toast.error("Download failed", "There may be no data for this selection.");
    }
  }

  function toggleStaff(id: string) {
    setPaStaff((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Weekend Work"
        actions={
          <Button variant="outline" onClick={exportXlsx} disabled={rows.length === 0}>
            Export Excel
          </Button>
        }
      />

      {/* Step 1 — pre-approval. */}
      <Card>
        <CardContent className="flex flex-col gap-3 pt-4">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold">Pre-approve a weekend</h2>
            <InfoHint text="Pick a Saturday or Sunday and the teachers allowed to come. Without pre-approval a teacher cannot claim weekend work." />
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="pa-date">Weekend date</Label>
              <Input
                id="pa-date"
                type="date"
                value={paDate}
                onChange={(e) => setPaDate(e.target.value)}
                className="w-44"
              />
            </div>
            <Button
              onClick={preapprove}
              disabled={paBusy || !paDate || paStaff.size === 0}
            >
              {paBusy ? "Saving…" : `Pre-approve ${paStaff.size || ""}`.trim()}
            </Button>
          </div>
          {paDate && !isWeekend(paDate) && (
            <p className="text-xs text-red-600 dark:text-red-400">
              That date is not a Saturday or Sunday.
            </p>
          )}
          <div className="flex max-h-44 flex-wrap gap-2 overflow-y-auto rounded-md border p-2">
            {staff.length === 0 ? (
              <span className="text-xs text-muted-foreground">No staff found.</span>
            ) : (
              staff.map((s) => (
                <label
                  key={s.id}
                  className="flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs"
                >
                  <input
                    type="checkbox"
                    checked={paStaff.has(s.id)}
                    onChange={() => toggleStaff(s.id)}
                  />
                  {s.first_name} {s.last_name}
                  <span className="text-muted-foreground">({s.emp_code})</span>
                </label>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="from">From</Label>
          <Input id="from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="w-40" />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="to">To</Label>
          <Input id="to" type="date" value={to} onChange={(e) => setTo(e.target.value)} className="w-40" />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="sf">Status</Label>
          <select
            id="sf"
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {STATUS_FILTERS.map((s) => (
              <option key={s || "all"} value={s}>{s || "All status"}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="tf">Teacher</Label>
          <select
            id="tf"
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={staffFilter}
            onChange={(e) => setStaffFilter(e.target.value)}
          >
            <option value="">All teachers</option>
            {staff.map((s) => (
              <option key={s.id} value={s.id}>
                {s.first_name} {s.last_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No weekend work for this selection. Pre-approve a weekend above to start.
        </p>
      ) : (
        <div className="rounded-xl border ring-1 ring-foreground/10 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Empcode</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>IN</TableHead>
                <TableHead>OUT</TableHead>
                <TableHead>Hours</TableHead>
                <TableHead>Work content</TableHead>
                <TableHead>Approved</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id} className={r.warning ? "bg-destructive/5" : undefined}>
                  <TableCell className="tabular-nums text-sm">{r.emp_code || "—"}</TableCell>
                  <TableCell className="font-medium">{r.name}</TableCell>
                  <TableCell className="whitespace-nowrap text-sm tabular-nums">{r.work_date}</TableCell>
                  <TableCell className="text-sm font-semibold">
                    {r.day_code}
                    {r.warning && <span title="Under 5h or missing punch" className="ml-1 text-red-600">⚠</span>}
                  </TableCell>
                  <TableCell className="text-sm tabular-nums">{r.time_in || "—"}</TableCell>
                  <TableCell className="text-sm tabular-nums">{r.time_out || "—"}</TableCell>
                  <TableCell className="text-sm tabular-nums">{hhmm(r.work_minutes)}</TableCell>
                  <TableCell className="max-w-xs text-xs text-muted-foreground">
                    {r.work_content || "—"}
                  </TableCell>
                  <TableCell>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_CHIP[r.approval_status] ?? ""}`}>
                      {r.approval_status}
                    </span>
                    {r.approval_note && (
                      <div className="mt-0.5 text-[11px] text-muted-foreground">{r.approval_note}</div>
                    )}
                    {r.approval_status === "APPROVED" && (
                      <div className="mt-0.5 text-[11px] text-muted-foreground">+{r.credit_days}d</div>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex flex-wrap justify-end gap-1">
                      {r.approval_status !== "APPROVED" && (
                        <Button
                          size="xs"
                          disabled={busyId !== null}
                          onClick={() =>
                            act(`/api/v1/admin/weekend-work/${r.id}/approve`, { note: null }, "Approved")
                          }
                        >
                          Approve
                        </Button>
                      )}
                      {r.approval_status !== "REJECTED" && (
                        <Button
                          size="xs"
                          variant="secondary"
                          disabled={busyId !== null}
                          onClick={() =>
                            act(`/api/v1/admin/weekend-work/${r.id}/reject`, { note: null }, "Rejected")
                          }
                        >
                          Reject
                        </Button>
                      )}
                      <Button
                        size="xs"
                        variant="outline"
                        disabled={busyId !== null}
                        onClick={() =>
                          act(
                            `/api/v1/admin/weekend-work/${r.id}/mark-absent`,
                            { absent: !r.marked_absent },
                            r.marked_absent ? "Absent cleared" : "Marked absent",
                          )
                        }
                      >
                        {r.marked_absent ? "Clear absent" : "Mark absent"}
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Rules note — same as the printed report footer. */}
      {rules.length > 0 && (
        <Card>
          <CardContent className="pt-4">
            <h3 className="text-sm font-semibold">Note</h3>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-muted-foreground">
              {rules.map((rule, i) => (
                <li key={i}>{rule}</li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
