"use client";

import { Card, CardContent } from "@/components/ui/card";
import type { ProductivityReportSummary } from "../_schemas/productivity-report";

function pct(v: number | null): string {
  return v == null ? "—" : `${v}%`;
}

export function ReportCards({ summary }: { summary: ProductivityReportSummary }) {
  return (
    <Card size="sm">
      <CardContent>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <Kpi label="Teachers" value={String(summary.teachers)} />
          <Kpi label="Total scheduled" value={String(summary.total_scheduled)} />
          <Kpi label="Total conducted" value={String(summary.total_conducted)} />
          <Kpi
            label="Completion"
            value={pct(summary.completion_pct)}
            tone={toneFor(summary.completion_pct, 90, 75)}
          />
          <Kpi
            label="Punctuality"
            value={pct(summary.punctuality_pct)}
            tone={toneFor(summary.punctuality_pct, 85, 70)}
          />
          <Kpi label="Total hours" value={`${summary.total_hours}h`} />
        </div>
      </CardContent>
    </Card>
  );
}

function toneFor(
  v: number | null,
  good: number,
  ok: number,
): "good" | "warn" | "bad" | undefined {
  if (v == null) return undefined;
  if (v >= good) return "good";
  if (v >= ok) return "warn";
  return "bad";
}

const TONE_CLASS: Record<"good" | "warn" | "bad", string> = {
  good: "text-emerald-600 dark:text-emerald-400",
  warn: "text-amber-600 dark:text-amber-400",
  bad: "text-destructive",
};

function Kpi({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "good" | "warn" | "bad";
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span
        className={`text-xl font-semibold tabular-nums ${tone ? TONE_CLASS[tone] : ""}`}
      >
        {value}
      </span>
    </div>
  );
}
