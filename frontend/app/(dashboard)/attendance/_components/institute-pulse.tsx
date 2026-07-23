"use client";

import { useMemo } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useBranchSummary } from "../_hooks/use-attendance";

type Tone = "good" | "warn" | "crit" | "neutral";

function valueTone(t: Tone): string {
  if (t === "good") return "text-emerald-600 dark:text-emerald-400";
  if (t === "warn") return "text-amber-600 dark:text-amber-400";
  if (t === "crit") return "text-destructive";
  return "text-foreground";
}

function stripeTone(t: Tone): string {
  if (t === "good") return "bg-emerald-500";
  if (t === "warn") return "bg-amber-500";
  if (t === "crit") return "bg-destructive";
  return "bg-transparent";
}

function pctTone(pct: number): Tone {
  if (pct >= 75) return "good";
  if (pct < 60) return "crit";
  return "warn";
}

// Always-visible institute pulse: the whole-branch snapshot for today, shown
// above the view rail so what needs attention reads before you navigate. Fed by
// the branch-summary snapshot (present rollup) plus the defaulter count lifted
// from the page so the nav badge and this tile never disagree.
export function InstitutePulse({
  branchId,
  today,
  defaultersCount,
  defaultersLoading,
}: {
  branchId: string | undefined;
  today: string;
  defaultersCount: number;
  defaultersLoading: boolean;
}) {
  const query = useBranchSummary(branchId, today, today);

  const t = useMemo(() => {
    let present = 0;
    let slots = 0;
    let batches = 0;
    for (const r of query.data ?? []) {
      if (r.working_days > 0) {
        present += r.present;
        slots += r.total_slots;
        batches += 1;
      }
    }
    const pct = slots > 0 ? (present / slots) * 100 : 0;
    return { present, slots, absent: slots - present, batches, pct };
  }, [query.data]);

  const loading = query.isLoading;
  const hasSession = t.slots > 0;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      <Tile
        label="Present today"
        loading={loading}
        value={hasSession ? `${t.pct.toFixed(0)}%` : "—"}
        sub={hasSession ? `${t.present} / ${t.slots} in session` : "no session today"}
        tone={hasSession ? pctTone(t.pct) : "neutral"}
      />
      <Tile
        label="Present / total"
        loading={loading}
        value={`${t.present} / ${t.slots}`}
        sub="students marked in"
        tone="neutral"
      />
      <Tile
        label="Absent"
        loading={loading}
        value={String(t.absent)}
        sub="parents auto-notified"
        tone={t.absent > 0 ? "crit" : "neutral"}
      />
      <Tile
        label="Batches in session"
        loading={loading}
        value={String(t.batches)}
        sub="scheduled today"
        tone="neutral"
      />
      <Tile
        label="Defaulters"
        loading={defaultersLoading}
        value={String(defaultersCount)}
        sub="below 75% this month"
        tone={defaultersCount > 0 ? "crit" : "good"}
      />
    </div>
  );
}

function Tile({
  label,
  value,
  sub,
  tone,
  loading,
}: {
  label: string;
  value: string;
  sub: string;
  tone: Tone;
  loading: boolean;
}) {
  return (
    <div className="relative overflow-hidden rounded-xl border bg-card p-4 shadow-sm ring-1 ring-foreground/10">
      <span
        aria-hidden
        className={cn("absolute inset-y-0 left-0 w-[3px]", stripeTone(tone))}
      />
      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      {loading ? (
        <Skeleton className="mt-1.5 h-7 w-16" />
      ) : (
        <div className={cn("mt-1 text-2xl font-semibold tabular-nums", valueTone(tone))}>
          {value}
        </div>
      )}
      <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>
    </div>
  );
}
