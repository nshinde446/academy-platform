"use client";

// KPI strip across the top of the Question Bank page. Numbers come
// from the existing /questions/count endpoint — one query per status.
// Tones match the MSA_Design palette: success for approved, default
// for total, warning-ish (default) for pending, muted for rejected.

interface Kpi {
  label: string;
  value: number | string;
  hint?: string;
  tone?: "default" | "success" | "warning" | "muted";
}

function toneClass(tone: Kpi["tone"]) {
  switch (tone) {
    case "success":
      return "text-[var(--success)]";
    case "warning":
      return "text-amber-600 dark:text-amber-400";
    case "muted":
      return "text-muted-foreground";
    default:
      return "";
  }
}

export function QBStatsStrip({ kpis }: { kpis: Kpi[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 rounded-xl border bg-card p-4 sm:grid-cols-3 lg:grid-cols-4">
      {kpis.map((k) => (
        <div key={k.label} className="flex flex-col gap-0.5">
          <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {k.label}
          </span>
          <span className={`text-2xl font-semibold tabular-nums ${toneClass(k.tone)}`}>
            {k.value}
          </span>
          {k.hint ? (
            <span className="text-xs text-muted-foreground">{k.hint}</span>
          ) : null}
        </div>
      ))}
    </div>
  );
}
