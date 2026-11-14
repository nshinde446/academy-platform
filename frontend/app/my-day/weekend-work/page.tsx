"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import apiClient, { apiErrorMessage } from "@/services/api-client";

interface WeekendRow {
  id: string;
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

const STATUS_CHIP: Record<string, string> = {
  PENDING: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  APPROVED: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  REJECTED: "bg-red-500/15 text-red-700 dark:text-red-300",
};

function ddmmyyyy(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}-${m}-${y}`;
}

function hhmm(minutes: number): string {
  const h = Math.floor((minutes || 0) / 60);
  const m = (minutes || 0) % 60;
  return `${h}:${String(m).padStart(2, "0")}`;
}

export default function PortalWeekendWorkPage() {
  const router = useRouter();
  const toast = useToast();
  const now = new Date();

  const [rows, setRows] = useState<WeekendRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let on = true;
    (async () => {
      setLoading(true);
      try {
        const res = await apiClient.get<WeekendRow[]>("/api/v1/me/weekend-work", {
          params: { year, month },
        });
        if (on) {
          setRows(res.data);
          setDrafts(
            Object.fromEntries(res.data.map((r) => [r.id, r.work_content ?? ""])),
          );
        }
      } catch (e) {
        if (apiErrorMessage(e, "") === "PASSWORD_CHANGE_REQUIRED")
          router.push("/change-password");
      } finally {
        if (on) setLoading(false);
      }
    })();
    return () => {
      on = false;
    };
  }, [year, month, tick, router]);

  async function save(id: string) {
    setSavingId(id);
    try {
      await apiClient.patch(`/api/v1/me/weekend-work/${id}`, {
        content: drafts[id] ?? "",
      });
      toast.success("Work content saved", "Your approver can now review it.");
      setTick((t) => t + 1);
    } catch (err) {
      toast.error("Could not save", apiErrorMessage(err, "Try again."));
    } finally {
      setSavingId(null);
    }
  }

  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  const years = Array.from({ length: 4 }, (_, i) => now.getFullYear() - i);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold leading-tight">Weekend Work</h1>
        <p className="text-sm text-muted-foreground">
          Days you were pre-approved to work on a Saturday or Sunday. Write what
          you did; your IN/OUT comes from the biometric punch. Minimum 5 hours of
          login is required, with a compulsory IN and OUT punch.
        </p>
      </div>

      <div className="flex gap-2">
        <select
          className="h-8 rounded-md border bg-background px-2 text-xs"
          value={month}
          onChange={(e) => setMonth(Number(e.target.value))}
        >
          {months.map((m, i) => (
            <option key={m} value={i + 1}>{m}</option>
          ))}
        </select>
        <select
          className="h-8 rounded-md border bg-background px-2 text-xs"
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
        >
          {years.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No pre-approved weekend work this month. A senior pre-approves the date
          before you can log weekend work.
        </p>
      ) : (
        rows.map((r) => {
          const approved = r.approval_status === "APPROVED";
          return (
            <Card key={r.id}>
              <CardContent className="flex flex-col gap-3 pt-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm font-medium">
                    {ddmmyyyy(r.work_date)}
                    <span className="ml-2 text-muted-foreground">
                      {r.day_code} · IN {r.time_in ?? "—"} · OUT {r.time_out ?? "—"} ·{" "}
                      {hhmm(r.work_minutes)} hrs
                    </span>
                  </div>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_CHIP[r.approval_status] ?? ""}`}
                  >
                    {r.approval_status}
                    {r.approval_note ? ` · ${r.approval_note}` : ""}
                  </span>
                </div>

                {r.warning && (
                  <p className="text-xs text-red-600 dark:text-red-400">
                    Under 5 hours or a missing IN/OUT punch — this may be marked
                    absent at management&apos;s discretion.
                  </p>
                )}

                <div className="flex flex-col gap-2">
                  <Label htmlFor={`wc-${r.id}`}>Work content</Label>
                  <textarea
                    id={`wc-${r.id}`}
                    className="min-h-20 rounded-md border bg-background px-3 py-2 text-sm disabled:opacity-60"
                    placeholder="e.g. 3 hours lecture, 2 hours preparation, 1 hour doubt solving"
                    value={drafts[r.id] ?? ""}
                    disabled={approved}
                    onChange={(e) =>
                      setDrafts((d) => ({ ...d, [r.id]: e.target.value }))
                    }
                  />
                  {!approved && (
                    <div>
                      <Button
                        size="sm"
                        onClick={() => save(r.id)}
                        disabled={savingId === r.id}
                      >
                        {savingId === r.id ? "Saving…" : "Save work content"}
                      </Button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })
      )}
    </div>
  );
}
