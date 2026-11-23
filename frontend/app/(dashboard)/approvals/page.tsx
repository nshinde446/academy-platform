"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { InfoHint } from "@/components/ui/info-hint";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import apiClient, { apiErrorMessage } from "@/services/api-client";
import { useBranchId } from "@/store/user-store";

type RecordType = "WEEKEND_PLAN" | "SELF_ASSESSMENT";

interface InboxRow {
  record_type: RecordType;
  record_id: string;
  teacher_name: string | null;
  emp_code: string | null;
  date: string;
  status: string;
  submitted_at: string | null;
  summary: string;
}

interface HistoryEntry {
  action: string;
  comment: string | null;
  by: string | null;
  at: string | null;
}

interface Detail {
  record_type: RecordType;
  record_id: string;
  teacher_name: string | null;
  emp_code: string | null;
  date: string;
  status: string;
  // weekend plan
  day_type?: string | null;
  holiday_name?: string | null;
  total_planned_minutes?: number;
  remarks?: string | null;
  items?: {
    work_type?: string; batch_name?: string | null; task_description?: string;
    start_time?: string; end_time?: string;
    item_name?: string; category_name?: string | null; selected_value?: string;
  }[];
  // self-assessment
  final_total_star?: number;
  miscellaneous_text?: string | null;
  stars?: { category_name: string | null; stars: number }[];
  history: HistoryEntry[];
}

const STATUS_CHIP: Record<string, string> = {
  PENDING: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  APPROVED: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  REJECTED: "bg-red-500/15 text-red-700 dark:text-red-300",
  ABSENT: "bg-zinc-500/15 text-zinc-700 dark:text-zinc-300",
  DRAFT: "bg-muted text-muted-foreground",
};

const TYPE_LABEL: Record<RecordType, string> = {
  WEEKEND_PLAN: "Weekend plan",
  SELF_ASSESSMENT: "Self-assessment",
};

const MIN_COMMENT = 10;

function monthRange(): { from: string; to: string } {
  const now = new Date();
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return {
    from: iso(new Date(now.getFullYear(), now.getMonth(), 1)),
    to: iso(new Date(now.getFullYear(), now.getMonth() + 1, 0)),
  };
}

export default function ApprovalsPage() {
  const { branchId } = useBranchId();
  const toast = useToast();
  const range = useMemo(() => monthRange(), []);

  const [typeFilter, setTypeFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("PENDING");
  const [from, setFrom] = useState(range.from);
  const [to, setTo] = useState(range.to);

  const [rows, setRows] = useState<InboxRow[]>([]);
  const [loading, setLoading] = useState(true);

  const [detail, setDetail] = useState<Detail | null>(null);
  const [action, setAction] = useState<"APPROVE" | "REJECT" | "MARK_ABSENT" | "">("");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!branchId) return;
    setLoading(true);
    try {
      const res = await apiClient.get<InboxRow[]>("/api/v1/admin/approvals", {
        params: {
          branch_id: branchId,
          type: typeFilter || undefined,
          status: statusFilter || undefined,
          from, to,
        },
      });
      setRows(res.data);
    } catch (e) {
      toast.error("Could not load the inbox", apiErrorMessage(e, "Try again."));
    } finally {
      setLoading(false);
    }
  }, [branchId, typeFilter, statusFilter, from, to, toast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  async function openDetail(r: InboxRow) {
    if (!branchId) return;
    setAction("");
    setComment("");
    try {
      const res = await apiClient.get<Detail>(
        `/api/v1/admin/approvals/${r.record_type}/${r.record_id}`,
        { params: { branch_id: branchId } },
      );
      setDetail(res.data);
    } catch (e) {
      toast.error("Could not open submission", apiErrorMessage(e, "Try again."));
    }
  }

  async function confirm() {
    if (!branchId || !detail || !action || comment.trim().length < MIN_COMMENT) return;
    setBusy(true);
    try {
      await apiClient.post(
        `/api/v1/admin/approvals/${detail.record_type}/${detail.record_id}/decide`,
        { action, comment: comment.trim() },
        { params: { branch_id: branchId } },
      );
      toast.success("Decision saved", "The teacher has been notified.");
      setDetail(null);
      setAction("");
      setComment("");
      await load();
    } catch (e) {
      toast.error("Could not save the decision", apiErrorMessage(e, "Try again."));
    } finally {
      setBusy(false);
    }
  }

  const canConfirm = !!action && comment.trim().length >= MIN_COMMENT && !busy;
  const isPending = detail?.status === "PENDING";

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Approvals"
        actions={
          <InfoHint text="Review teachers' weekend plans and daily self-assessments. Every decision needs a written comment the teacher can see." />
        }
      />

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="tf">Type</Label>
          <select id="tf" className="h-9 rounded-md border bg-background px-2 text-sm"
            value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="">All types</option>
            <option value="WEEKEND_PLAN">Weekend plans</option>
            <option value="SELF_ASSESSMENT">Self-assessments</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="sf">Status</Label>
          <select id="sf" className="h-9 rounded-md border bg-background px-2 text-sm"
            value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="PENDING">Pending</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
            <option value="ABSENT">Absent</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="from">From</Label>
          <Input id="from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="w-40" />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="to">To</Label>
          <Input id="to" type="date" value={to} onChange={(e) => setTo(e.target.value)} className="w-40" />
        </div>
      </div>

      {/* Detail + action panel */}
      {detail && (
        <Card>
          <CardContent className="flex flex-col gap-4 pt-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-semibold">
                {TYPE_LABEL[detail.record_type]} · {detail.teacher_name} ({detail.emp_code}) · {detail.date}
              </div>
              <div className="flex items-center gap-2">
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_CHIP[detail.status] ?? ""}`}>
                  {detail.status}
                </span>
                <button className="text-xs text-muted-foreground underline" onClick={() => setDetail(null)}>
                  Close
                </button>
              </div>
            </div>

            {/* Weekend plan body */}
            {detail.record_type === "WEEKEND_PLAN" && (
              <div className="flex flex-col gap-1 text-sm">
                <div className="text-xs text-muted-foreground">
                  {detail.day_type}{detail.holiday_name ? ` · ${detail.holiday_name}` : ""}
                  {typeof detail.total_planned_minutes === "number"
                    ? ` · ${Math.floor(detail.total_planned_minutes / 60)}h ${detail.total_planned_minutes % 60}m planned`
                    : ""}
                </div>
                <ul className="mt-1 flex flex-col gap-1 text-xs">
                  {detail.items?.map((it, i) => (
                    <li key={i} className="rounded border px-2 py-1">
                      {it.start_time}–{it.end_time} · {it.work_type}
                      {it.batch_name ? ` · ${it.batch_name}` : ""} · {it.task_description}
                    </li>
                  ))}
                </ul>
                {detail.remarks && <p className="text-xs text-muted-foreground">Remarks: {detail.remarks}</p>}
              </div>
            )}

            {/* Self-assessment body */}
            {detail.record_type === "SELF_ASSESSMENT" && (
              <div className="flex flex-col gap-2 text-sm">
                <div className="font-semibold">
                  Final Total Star: {detail.final_total_star} / 20
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  {detail.stars?.map((s, i) => (
                    <span key={i} className="rounded border px-2 py-1">
                      {s.category_name}: {s.stars}★
                    </span>
                  ))}
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  {detail.items?.map((it, i) => (
                    <span key={i} className="rounded border px-2 py-0.5">
                      {it.category_name} · {it.item_name}: {it.selected_value}
                    </span>
                  ))}
                </div>
                {detail.miscellaneous_text && (
                  <p className="text-xs text-muted-foreground">Misc: {detail.miscellaneous_text}</p>
                )}
              </div>
            )}

            {/* History */}
            {detail.history.length > 0 && (
              <div className="flex flex-col gap-1">
                <div className="text-xs font-semibold text-muted-foreground">History</div>
                <ul className="flex flex-col gap-0.5 text-xs text-muted-foreground">
                  {detail.history.map((h, i) => (
                    <li key={i}>
                      {h.action}{h.by ? ` · ${h.by}` : ""}{h.comment ? ` · “${h.comment}”` : ""}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Action panel — only for pending submissions */}
            {isPending ? (
              <div className="flex flex-col gap-3 border-t pt-3">
                <div className="flex flex-wrap gap-2">
                  <Button size="sm"
                    variant={action === "APPROVE" ? "default" : "outline"}
                    onClick={() => setAction("APPROVE")}>Approve</Button>
                  <Button size="sm"
                    variant={action === "REJECT" ? "destructive" : "outline"}
                    onClick={() => setAction("REJECT")}>Reject</Button>
                  <Button size="sm"
                    variant={action === "MARK_ABSENT" ? "secondary" : "outline"}
                    onClick={() => setAction("MARK_ABSENT")}>Mark absent</Button>
                </div>
                <div className="flex flex-col gap-1">
                  <Label htmlFor="cmt" className="text-xs">
                    Comment (required, min {MIN_COMMENT} characters)
                  </Label>
                  <textarea id="cmt" value={comment} onChange={(e) => setComment(e.target.value)}
                    className="min-h-16 rounded-md border bg-background px-3 py-2 text-sm"
                    placeholder="Reason for the decision — the teacher will see this." />
                  <span className="text-[11px] text-muted-foreground">
                    {comment.trim().length}/{MIN_COMMENT}
                  </span>
                </div>
                <div>
                  <Button disabled={!canConfirm} onClick={confirm}>
                    {busy ? "Saving…" : "Confirm decision"}
                  </Button>
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground border-t pt-3">
                This submission is {detail.status.toLowerCase()} — the decision is final.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Inbox table */}
      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing to review for this selection.</p>
      ) : (
        <div className="rounded-xl border ring-1 ring-foreground/10 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Teacher</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Summary</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={`${r.record_type}-${r.record_id}`}>
                  <TableCell className="whitespace-nowrap text-sm tabular-nums">{r.date}</TableCell>
                  <TableCell className="font-medium">
                    {r.teacher_name} <span className="text-muted-foreground">({r.emp_code})</span>
                  </TableCell>
                  <TableCell className="text-sm">{TYPE_LABEL[r.record_type]}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{r.summary}</TableCell>
                  <TableCell>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_CHIP[r.status] ?? ""}`}>
                      {r.status}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button size="xs" onClick={() => openDetail(r)}>Review</Button>
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
