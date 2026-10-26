"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import apiClient, { apiErrorMessage } from "@/services/api-client";

type Range = "week" | "month" | "quarter" | "year";
const RANGES: Range[] = ["week", "month", "quarter", "year"];

interface Bucket {
  label: string;
  lectures: number;
  on_time: number;
  delayed: number;
  on_time_pct: number | null;
  late_minutes: number;
  present_days: number;
}
interface Totals {
  lectures: number;
  on_time: number;
  delayed: number;
  on_time_pct: number | null;
  delay_minutes: number;
  scheduled_minutes: number;
  delivered_minutes: number;
  present_days: number;
  absent_days: number;
  late_count: number;
  late_minutes: number;
}
interface Productivity {
  range: Range;
  start: string;
  end: string;
  is_teacher: boolean;
  totals: Totals;
  buckets: Bucket[];
}

export default function PortalProductivityPage() {
  const router = useRouter();
  const [range, setRange] = useState<Range>("month");
  const [data, setData] = useState<Productivity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(
    async (r: Range) => {
      setLoading(true);
      setError("");
      try {
        const res = await apiClient.get<Productivity>("/api/v1/me/productivity", {
          params: { range: r },
        });
        setData(res.data);
      } catch (e) {
        const msg = apiErrorMessage(e, "Could not load your productivity.");
        if (msg === "PASSWORD_CHANGE_REQUIRED") router.push("/change-password");
        else setError(msg);
      } finally {
        setLoading(false);
      }
    },
    [router],
  );

  useEffect(() => {
    // load() sets state only after an await (not synchronously).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load(range);
  }, [range, load]);

  const t = data?.totals;
  const hrs = (min: number) => (min / 60).toFixed(1);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold leading-tight">Productivity</h1>
        <p className="text-sm text-muted-foreground">
          Your lectures, punctuality and attendance. Factual figures only.
        </p>
      </div>

      {/* Range toggle */}
      <div className="flex gap-1.5">
        {RANGES.map((r) => (
          <button
            key={r}
            onClick={() => setRange(r)}
            className={`rounded-md border px-3 py-1 text-[13px] capitalize transition-colors ${
              range === r
                ? "border-primary bg-primary/10 font-medium text-foreground"
                : "border-border text-muted-foreground hover:bg-muted"
            }`}
          >
            {r}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : data && t ? (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <Stat label="Lectures" value={t.lectures} />
            <Stat label="On-time %" value={t.on_time_pct == null ? "—" : `${t.on_time_pct}%`} />
            <Stat label="Delayed" value={t.delayed} />
            <Stat label="Late mins" value={t.late_minutes} />
            <Stat label="Present days" value={t.present_days} />
            <Stat label="Teaching hrs" value={hrs(t.delivered_minutes)} />
          </div>

          {!data.is_teacher && (
            <p className="text-xs text-muted-foreground">
              Lecture figures apply to teaching staff; your attendance figures are shown above.
            </p>
          )}

          {/* Charts */}
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard
              title="Lectures"
              buckets={data.buckets}
              value={(b) => b.lectures}
              color="bg-primary"
            />
            <ChartCard
              title="On-time %"
              buckets={data.buckets}
              value={(b) => b.on_time_pct ?? 0}
              max={100}
              suffix="%"
              color="bg-emerald-500"
            />
          </div>
        </>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border bg-card px-3 py-3 text-center">
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
    </div>
  );
}

function ChartCard({
  title,
  buckets,
  value,
  max,
  suffix = "",
  color,
}: {
  title: string;
  buckets: Bucket[];
  value: (b: Bucket) => number;
  max?: number;
  suffix?: string;
  color: string;
}) {
  const vals = buckets.map(value);
  const top = max ?? Math.max(1, ...vals);
  return (
    <Card>
      <CardContent className="pt-5">
        <h2 className="mb-4 text-sm font-semibold">{title}</h2>
        {buckets.length === 0 ? (
          <p className="text-sm text-muted-foreground">No data for this range.</p>
        ) : (
          <div className="flex h-40 items-end gap-1.5">
            {buckets.map((b, i) => {
              const v = vals[i];
              const pct = top > 0 ? Math.round((v / top) * 100) : 0;
              return (
                <div key={b.label + i} className="flex min-w-0 flex-1 flex-col items-center gap-1">
                  <div className="flex w-full flex-1 items-end">
                    <div
                      className={`w-full rounded-t ${color}`}
                      style={{ height: `${pct}%` }}
                      title={`${b.label}: ${v}${suffix}`}
                    />
                  </div>
                  <span className="w-full truncate text-center text-[10px] tabular-nums text-foreground">
                    {v}
                    {suffix}
                  </span>
                  <span className="w-full truncate text-center text-[10px] text-muted-foreground">
                    {b.label}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
