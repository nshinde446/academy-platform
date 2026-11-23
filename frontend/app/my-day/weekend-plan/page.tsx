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

type Status = "DRAFT" | "PENDING" | "APPROVED" | "REJECTED" | "ABSENT";

interface PlanItem {
  id?: string;
  work_type: string;
  batch_id: string | null;
  task_description: string;
  start_time: string;
  end_time: string;
}

interface HistoryEntry {
  action: string;
  comment: string | null;
  by: string | null;
  at: string | null;
}

interface Plan {
  id: string;
  plan_date: string;
  day_type: string | null;
  holiday_name: string | null;
  status: Status;
  total_planned_minutes: number;
  remarks: string | null;
  latest_approver_comment: string | null;
  can_edit: boolean;
  items: PlanItem[];
  history?: HistoryEntry[];
}

interface Meta {
  holidays: { date: string; name: string }[];
  batches: { id: string; name: string }[];
  work_types: string[];
  default_approver: { id: string; name: string } | null;
}

const STATUS_CHIP: Record<Status, string> = {
  DRAFT: "bg-muted text-muted-foreground",
  PENDING: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  APPROVED: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  REJECTED: "bg-red-500/15 text-red-700 dark:text-red-300",
  ABSENT: "bg-zinc-500/15 text-zinc-700 dark:text-zinc-300",
};

function ddmmyyyy(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}-${m}-${y}`;
}

function hhmm(minutes: number): string {
  const h = Math.floor((minutes || 0) / 60);
  const m = (minutes || 0) % 60;
  return `${h}h${m ? ` ${m}m` : ""}`;
}

// 15-minute-step time options, 06:00 → 22:00 (SRD: time dropdown, 15-min steps).
const TIME_OPTIONS: string[] = (() => {
  const out: string[] = [];
  for (let h = 6; h <= 22; h++)
    for (const m of [0, 15, 30, 45])
      out.push(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`);
  return out;
})();

function emptyItem(): PlanItem {
  return { work_type: "Lecture", batch_id: null, task_description: "", start_time: "09:00", end_time: "11:00" };
}

export default function PortalWeekendPlanPage() {
  const router = useRouter();
  const toast = useToast();
  const now = new Date();

  const [meta, setMeta] = useState<Meta | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [tick, setTick] = useState(0);

  // form state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [planDate, setPlanDate] = useState("");
  const [remarks, setRemarks] = useState("");
  const [items, setItems] = useState<PlanItem[]>([emptyItem()]);
  const [saving, setSaving] = useState(false);

  const [toWithdraw, setToWithdraw] = useState<Plan | null>(null);
  const [toDelete, setToDelete] = useState<Plan | null>(null);

  useEffect(() => {
    let on = true;
    (async () => {
      try {
        const [m, list] = await Promise.all([
          apiClient.get<Meta>("/api/v1/me/weekend-plan-meta", { params: { year, month } }),
          apiClient.get<Plan[]>("/api/v1/me/weekend-plans", { params: { year, month } }),
        ]);
        if (on) {
          setMeta(m.data);
          setPlans(list.data);
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
  }, [year, month, tick, router]);

  function resetForm() {
    setEditingId(null);
    setPlanDate("");
    setRemarks("");
    setItems([emptyItem()]);
  }

  function startEdit(p: Plan) {
    setEditingId(p.id);
    setPlanDate(p.plan_date);
    setRemarks(p.remarks ?? "");
    setItems(p.items.length ? p.items.map((i) => ({ ...i })) : [emptyItem()]);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function patchItem(idx: number, patch: Partial<PlanItem>) {
    setItems((xs) => xs.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  }

  function body() {
    return {
      plan_date: planDate,
      remarks: remarks.trim() || null,
      approver_id: null,
      items: items.map((it) => ({
        work_type: it.work_type,
        batch_id: it.batch_id || null,
        task_description: it.task_description.trim(),
        start_time: it.start_time,
        end_time: it.end_time,
      })),
    };
  }

  async function save(submit: boolean) {
    if (!planDate) {
      toast.error("Pick a date", "Choose the Saturday, Sunday or holiday you plan to work.");
      return;
    }
    if (submit && items.some((it) => !it.task_description.trim())) {
      toast.error("Describe each line", "Every work line needs a short task description.");
      return;
    }
    setSaving(true);
    try {
      if (editingId) {
        await apiClient.put(`/api/v1/me/weekend-plans/${editingId}`, body(), { params: { submit } });
      } else {
        await apiClient.post("/api/v1/me/weekend-plans", body(), { params: { submit } });
      }
      toast.success(submit ? "Submitted for approval" : "Draft saved");
      resetForm();
      setTick((t) => t + 1);
    } catch (err) {
      toast.error("Could not save", apiErrorMessage(err, "Check the dates and times and try again."));
    } finally {
      setSaving(false);
    }
  }

  async function submitExisting(p: Plan) {
    try {
      await apiClient.post(`/api/v1/me/weekend-plans/${p.id}/submit`);
      toast.success("Submitted for approval");
      setTick((t) => t + 1);
    } catch (err) {
      toast.error("Could not submit", apiErrorMessage(err, "Try again."));
    }
  }

  async function confirmWithdraw() {
    if (!toWithdraw) return;
    try {
      await apiClient.post(`/api/v1/me/weekend-plans/${toWithdraw.id}/withdraw`);
      toast.success("Plan withdrawn", "It is back to draft and editable.");
      setTick((t) => t + 1);
    } catch (err) {
      toast.error("Could not withdraw", apiErrorMessage(err, "Try again."));
    } finally {
      setToWithdraw(null);
    }
  }

  async function confirmDelete() {
    if (!toDelete) return;
    try {
      await apiClient.delete(`/api/v1/me/weekend-plans/${toDelete.id}`);
      toast.success("Draft deleted");
      setTick((t) => t + 1);
    } catch (err) {
      toast.error("Could not delete", apiErrorMessage(err, "Try again."));
    } finally {
      setToDelete(null);
    }
  }

  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const years = Array.from({ length: 4 }, (_, i) => now.getFullYear() - i);
  const batchName = (id: string | null) => meta?.batches.find((b) => b.id === id)?.name;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold leading-tight">Weekend / Holiday Work Plan</h1>
        <p className="text-sm text-muted-foreground">
          Plan work on a Saturday, Sunday or academy holiday and send it to your
          approver. Add each piece of work as a line; your approver reviews the
          plan and always leaves a comment.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,26rem)_1fr]">
        {/* Plan form */}
        <Card>
          <CardContent className="pt-5">
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">
                  {editingId ? "Edit plan" : "New plan"}
                </h2>
                {editingId && (
                  <button className="text-xs text-muted-foreground underline" onClick={resetForm}>
                    Cancel edit
                  </button>
                )}
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="pdate">Date (Saturday, Sunday or holiday)</Label>
                <Input id="pdate" type="date" value={planDate}
                  onChange={(e) => setPlanDate(e.target.value)} />
                {meta && meta.holidays.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    Holidays this month: {meta.holidays.map((h) => `${ddmmyyyy(h.date)} (${h.name})`).join(", ")}
                  </p>
                )}
              </div>

              <div className="flex flex-col gap-3">
                <Label>Work lines</Label>
                {items.map((it, idx) => (
                  <div key={idx} className="flex flex-col gap-2 rounded-md border p-3">
                    <div className="flex gap-2">
                      <select className="h-9 flex-1 rounded-md border bg-background px-2 text-sm"
                        value={it.work_type} onChange={(e) => patchItem(idx, { work_type: e.target.value })}>
                        {(meta?.work_types ?? ["Lecture"]).map((w) => (
                          <option key={w} value={w}>{w}</option>
                        ))}
                      </select>
                      <select className="h-9 flex-1 rounded-md border bg-background px-2 text-sm"
                        value={it.batch_id ?? ""} onChange={(e) => patchItem(idx, { batch_id: e.target.value || null })}>
                        <option value="">Batch / class…</option>
                        {(meta?.batches ?? []).map((b) => (
                          <option key={b.id} value={b.id}>{b.name}</option>
                        ))}
                      </select>
                    </div>
                    <Input type="text" placeholder="Topic / task"
                      value={it.task_description}
                      onChange={(e) => patchItem(idx, { task_description: e.target.value })} maxLength={500} />
                    <div className="flex items-center gap-2">
                      <select className="h-9 flex-1 rounded-md border bg-background px-2 text-sm"
                        value={it.start_time} onChange={(e) => patchItem(idx, { start_time: e.target.value })}>
                        {TIME_OPTIONS.map((t) => <option key={t} value={t}>{t}</option>)}
                      </select>
                      <span className="text-xs text-muted-foreground">to</span>
                      <select className="h-9 flex-1 rounded-md border bg-background px-2 text-sm"
                        value={it.end_time} onChange={(e) => patchItem(idx, { end_time: e.target.value })}>
                        {TIME_OPTIONS.map((t) => <option key={t} value={t}>{t}</option>)}
                      </select>
                      {items.length > 1 && (
                        <button className="text-xs text-red-600 underline"
                          onClick={() => setItems((xs) => xs.filter((_, i) => i !== idx))}>
                          Remove
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                <Button type="button" variant="secondary" size="sm"
                  onClick={() => setItems((xs) => [...xs, emptyItem()])}>
                  + Add work line
                </Button>
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="rem">Remarks (optional)</Label>
                <Input id="rem" type="text" value={remarks}
                  onChange={(e) => setRemarks(e.target.value)} maxLength={500} />
              </div>

              {meta?.default_approver && (
                <p className="text-xs text-muted-foreground">
                  Approver: {meta.default_approver.name}
                </p>
              )}

              <div className="flex gap-2">
                <Button variant="secondary" disabled={saving} onClick={() => save(false)}>
                  {saving ? "Saving…" : "Save draft"}
                </Button>
                <Button disabled={saving} onClick={() => save(true)}>
                  {saving ? "Submitting…" : "Submit for approval"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* My plans */}
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">My plans</h2>
            <div className="flex gap-2">
              <select className="h-8 rounded-md border bg-background px-2 text-xs"
                value={month} onChange={(e) => setMonth(Number(e.target.value))}>
                {months.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
              </select>
              <select className="h-8 rounded-md border bg-background px-2 text-xs"
                value={year} onChange={(e) => setYear(Number(e.target.value))}>
                {years.map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
          </div>

          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : plans.length === 0 ? (
            <p className="text-sm text-muted-foreground">No weekend plans for this month yet.</p>
          ) : (
            plans.map((p) => (
              <Card key={p.id}>
                <CardContent className="flex flex-col gap-3 pt-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-medium">
                      {ddmmyyyy(p.plan_date)}
                      <span className="ml-2 text-muted-foreground">
                        {p.day_type}{p.holiday_name ? ` · ${p.holiday_name}` : ""} · {hhmm(p.total_planned_minutes)} planned
                      </span>
                    </div>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_CHIP[p.status]}`}>
                      {p.status}
                    </span>
                  </div>

                  <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
                    {p.items.map((it, i) => (
                      <li key={i}>
                        {it.start_time}–{it.end_time} · {it.work_type}
                        {batchName(it.batch_id) ? ` · ${batchName(it.batch_id)}` : ""} · {it.task_description}
                      </li>
                    ))}
                  </ul>

                  {p.latest_approver_comment && (
                    <p className={`text-xs ${p.status === "REJECTED" ? "text-red-600 dark:text-red-400" : "text-foreground"}`}>
                      Approver: {p.latest_approver_comment}
                    </p>
                  )}

                  <div className="flex flex-wrap gap-2">
                    {p.can_edit && (
                      <Button size="sm" variant="secondary" onClick={() => startEdit(p)}>
                        {p.status === "REJECTED" ? "Edit & resubmit" : "Edit"}
                      </Button>
                    )}
                    {p.status === "DRAFT" && (
                      <>
                        <Button size="sm" onClick={() => submitExisting(p)}>Submit</Button>
                        <Button size="sm" variant="secondary" onClick={() => setToDelete(p)}>Delete</Button>
                      </>
                    )}
                    {p.status === "PENDING" && (
                      <Button size="sm" variant="secondary" onClick={() => setToWithdraw(p)}>Withdraw</Button>
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
        title="Withdraw this plan?"
        description="This pulls the plan back to draft before your approver acts. You can edit and resubmit it."
        confirmLabel="Withdraw"
        onConfirm={confirmWithdraw}
      />
      <ConfirmDialog
        open={!!toDelete}
        onOpenChange={(o) => !o && setToDelete(null)}
        title="Delete this draft?"
        description="This removes the draft plan. This cannot be undone."
        confirmLabel="Delete"
        onConfirm={confirmDelete}
      />
    </div>
  );
}
