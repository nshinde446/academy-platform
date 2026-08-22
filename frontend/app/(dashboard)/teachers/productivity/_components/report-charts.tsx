"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import type {
  ProductivityReportBatchRow,
  ProductivityReportResponse,
  ProductivityReportSubjectRow,
  ProductivityReportTeacherRow,
  ProductivityReportTrendPoint,
} from "../_schemas/productivity-report";

type Metric = "conducted" | "hours" | "completion_pct";

const METRIC_LABEL: Record<Metric, string> = {
  conducted: "Lectures",
  hours: "Hours",
  completion_pct: "Completion %",
};

type DimRow = ProductivityReportSubjectRow | ProductivityReportBatchRow;

function metricValue(r: DimRow, m: Metric): number {
  if (m === "hours") return r.hours;
  if (m === "completion_pct") return r.completion_pct ?? 0;
  return r.conducted;
}

function metricDisplay(r: DimRow, m: Metric): string {
  if (m === "hours") return `${r.hours}h`;
  if (m === "completion_pct") return r.completion_pct == null ? "—" : `${r.completion_pct}%`;
  return String(r.conducted);
}

// ── Horizontal CSS-bar chart with a metric toggle (subject / batch) ──────────

function DimChart({
  title,
  rows,
  nameOf,
}: {
  title: string;
  rows: DimRow[];
  nameOf: (r: DimRow) => string;
}) {
  const [metric, setMetric] = useState<Metric>("conducted");
  const max = Math.max(1, ...rows.map((r) => metricValue(r, metric)));

  return (
    <Card size="sm">
      <CardContent>
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">{title}</h3>
          <div className="flex gap-1">
            {(Object.keys(METRIC_LABEL) as Metric[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMetric(m)}
                className={`rounded-md px-2 py-0.5 text-[11px] ${
                  metric === m
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {METRIC_LABEL[m]}
              </button>
            ))}
          </div>
        </div>
        {rows.length === 0 ? (
          <p className="text-xs text-muted-foreground">No data.</p>
        ) : (
          <div className="flex flex-col gap-1.5">
            {rows.map((r, i) => {
              const v = metricValue(r, metric);
              return (
                <div key={i} className="flex items-center gap-2">
                  <span className="w-28 shrink-0 truncate text-xs" title={nameOf(r)}>
                    {nameOf(r)}
                  </span>
                  <div className="h-4 flex-1 overflow-hidden rounded bg-muted">
                    <div
                      className="h-full rounded bg-primary/70"
                      style={{ width: `${(v / max) * 100}%` }}
                    />
                  </div>
                  <span className="w-12 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                    {metricDisplay(r, metric)}
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

// ── Scheduled vs Conducted grouped vertical bars (top teachers) ──────────────

function ScheduledVsActual({
  rows,
}: {
  rows: ProductivityReportTeacherRow[];
}) {
  const top = [...rows].sort((a, b) => b.scheduled - a.scheduled).slice(0, 10);
  const max = Math.max(1, ...top.map((r) => r.scheduled));

  return (
    <Card size="sm">
      <CardContent>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Scheduled vs Conducted</h3>
          <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
            <Legend className="bg-primary/30" label="Scheduled" />
            <Legend className="bg-primary" label="Conducted" />
          </div>
        </div>
        {top.length === 0 ? (
          <p className="text-xs text-muted-foreground">No data.</p>
        ) : (
          <div className="flex h-48 items-end gap-2">
            {top.map((t) => (
              <div
                key={t.teacher_id}
                className="flex flex-1 flex-col items-center gap-1"
                title={`${t.first_name} ${t.last_name}: ${t.conducted}/${t.scheduled}`}
              >
                <div className="flex h-40 w-full items-end justify-center gap-0.5">
                  <div
                    className="w-1/2 rounded-t bg-primary/30"
                    style={{ height: `${(t.scheduled / max) * 100}%` }}
                  />
                  <div
                    className="w-1/2 rounded-t bg-primary"
                    style={{ height: `${(t.conducted / max) * 100}%` }}
                  />
                </div>
                <span className="w-full truncate text-center text-[10px] text-muted-foreground">
                  {t.last_name || t.first_name}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Legend({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className={`inline-block h-2 w-2 rounded-sm ${className}`} />
      {label}
    </span>
  );
}

// ── Week-wise trend (SVG line: completion % + punctuality %) ─────────────────

function TrendChart({ trend }: { trend: ProductivityReportTrendPoint[] }) {
  const W = 640;
  const H = 200;
  const padX = 36;
  const padY = 20;
  const n = trend.length;

  function x(i: number): number {
    if (n <= 1) return padX;
    return padX + (i * (W - 2 * padX)) / (n - 1);
  }
  function y(v: number): number {
    // 0–100 percentage scale, inverted for SVG.
    return padY + ((100 - v) * (H - 2 * padY)) / 100;
  }

  function line(pick: (p: ProductivityReportTrendPoint) => number | null): string {
    return trend
      .map((p, i) => {
        const v = pick(p);
        if (v == null) return null;
        return `${x(i)},${y(v)}`;
      })
      .filter((s): s is string => s !== null)
      .join(" ");
  }

  return (
    <Card size="sm">
      <CardContent>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Week-wise trend</h3>
          <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
            <Legend className="bg-blue-500" label="Completion %" />
            <Legend className="bg-amber-500" label="Punctuality %" />
          </div>
        </div>
        {n === 0 ? (
          <p className="text-xs text-muted-foreground">No data.</p>
        ) : (
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="w-full"
            role="img"
            aria-label="Week-wise completion and punctuality trend"
          >
            {[0, 25, 50, 75, 100].map((g) => (
              <g key={g}>
                <line
                  x1={padX}
                  x2={W - padX}
                  y1={y(g)}
                  y2={y(g)}
                  className="stroke-border"
                  strokeWidth={1}
                />
                <text x={4} y={y(g) + 3} className="fill-muted-foreground text-[9px]">
                  {g}
                </text>
              </g>
            ))}
            <polyline
              points={line((p) => p.completion_pct)}
              fill="none"
              className="stroke-blue-500"
              strokeWidth={2}
            />
            <polyline
              points={line((p) => p.punctuality_pct)}
              fill="none"
              className="stroke-amber-500"
              strokeWidth={2}
            />
            {trend.map((p, i) => (
              <text
                key={i}
                x={x(i)}
                y={H - 4}
                textAnchor="middle"
                className="fill-muted-foreground text-[9px]"
              >
                {p.label.slice(5)}
              </text>
            ))}
          </svg>
        )}
      </CardContent>
    </Card>
  );
}

export function ReportCharts({ report }: { report: ProductivityReportResponse }) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <ScheduledVsActual rows={report.by_teacher} />
      <TrendChart trend={report.trend} />
      <DimChart
        title="Subject-wise"
        rows={report.by_subject}
        nameOf={(r) => (r as ProductivityReportSubjectRow).subject_name}
      />
      <DimChart
        title="Batch-wise"
        rows={report.by_batch}
        nameOf={(r) => (r as ProductivityReportBatchRow).batch_name}
      />
    </div>
  );
}
