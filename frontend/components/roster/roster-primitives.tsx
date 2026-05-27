// Small visual building blocks shared by the Students + Teachers
// roster tables (MSA_Design alignment, Phase B). Keep these dumb and
// presentational so the page-level table components stay focused on
// data flow.

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

/** Initials-bubble avatar shown in the leftmost cell of each roster row. */
export function RosterAvatar({
  first,
  last,
  className,
}: {
  first: string;
  last: string;
  className?: string;
}) {
  const initials = `${first?.[0] ?? ""}${last?.[0] ?? ""}`.toUpperCase();
  return (
    <span
      className={cn(
        "inline-flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary",
        className,
      )}
      aria-hidden
    >
      {initials || "?"}
    </span>
  );
}

/**
 * Score cell — colours by threshold:
 *   ≥ 70%  → success (green)
 *   < 50%  → destructive (red)
 *   else   → default foreground
 *
 * Set tone="muted" for secondary metrics (DPP) so they stay quiet
 * against the primary Avg score column.
 */
export function ScoreCell({
  value,
  tone = "primary",
  className,
}: {
  value: number;
  tone?: "primary" | "muted";
  className?: string;
}) {
  const color =
    tone === "muted"
      ? "text-muted-foreground"
      : value >= 70
        ? "text-[var(--success)]"
        : value < 50
          ? "text-destructive"
          : "";
  return (
    <span className={cn("tabular-nums", color, className)}>
      {value.toFixed(0)}%
    </span>
  );
}

/** Right-aligned tabular-number cell wrapper. */
export function NumCell({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span className={cn("tabular-nums", className)}>{children}</span>
  );
}

/** Fees badge — maps the four allowed values to green/red/amber pills. */
export function FeesBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-muted-foreground">—</span>;
  const variant: "success" | "destructive" | "secondary" =
    status === "paid"
      ? "success"
      : status === "overdue"
        ? "destructive"
        : "secondary";
  const label = status === "due" ? "Due" : status === "overdue" ? "Overdue" : status === "partial" ? "Partial" : "Paid";
  return <Badge variant={variant}>{label}</Badge>;
}
