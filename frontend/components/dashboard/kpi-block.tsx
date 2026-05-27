// MSA_Design KPI block + grid. One outer card contains many KPIs in
// an auto-fit grid; each KPI is a tiny stack (uppercase label, big
// 28px value, muted hint). Tone variants colour just the value.

import { cn } from "@/lib/utils";

export type KpiTone =
  | "default"
  | "success"
  | "warning"
  | "destructive"
  | "primary";

interface KpiBlockProps {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: KpiTone;
  className?: string;
}

const TONE: Record<KpiTone, string> = {
  default: "",
  primary: "text-[var(--primary)]",
  success: "text-[var(--success)]",
  warning: "text-[var(--warning)]",
  destructive: "text-destructive",
};

export function KpiBlock({
  label,
  value,
  hint,
  tone = "default",
  className,
}: KpiBlockProps) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span className="text-[11px] font-medium uppercase tracking-[0.06em] text-muted-foreground">
        {label}
      </span>
      <span
        className={cn(
          "text-[28px] font-semibold leading-[1.1] tabular-nums tracking-tight",
          TONE[tone],
        )}
      >
        {value}
      </span>
      {hint ? (
        <span className="text-[11.5px] text-muted-foreground">{hint}</span>
      ) : null}
    </div>
  );
}

/** Auto-fit grid wrapper. Matches MSA `.kpi-grid` (140px min cols). */
export function KpiGrid({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn("grid gap-3", className)}
      style={{ gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }}
    >
      {children}
    </div>
  );
}

/** Section label — uppercase tracking matches MSA `.section-label`. */
export function SectionLabel({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <h3
      className={cn(
        "text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground",
        className,
      )}
    >
      {children}
    </h3>
  );
}
