"use client";

import { Card, CardContent } from "@/components/ui/card";
import type { RosterSnapshot } from "../_schemas/roster";

interface SnapshotStripProps {
  snapshot: RosterSnapshot;
}

interface Tile {
  label: string;
  value: number;
  tone: "default" | "success" | "warning" | "destructive";
}

const TONE_CLASS: Record<Tile["tone"], string> = {
  default: "text-foreground",
  success: "text-emerald-600 dark:text-emerald-400",
  warning: "text-amber-600 dark:text-amber-400",
  destructive: "text-destructive",
};

export function SnapshotStrip({ snapshot }: SnapshotStripProps) {
  const tiles: Tile[] = [
    { label: "Planned", value: snapshot.planned, tone: "default" },
    { label: "Done", value: snapshot.completed, tone: "success" },
    { label: "Live", value: snapshot.in_progress, tone: "default" },
    { label: "Pending", value: snapshot.pending, tone: "default" },
    {
      label: "Teacher no-show",
      value: snapshot.no_show_teacher,
      tone: snapshot.no_show_teacher > 0 ? "destructive" : "default",
    },
    { label: "Cancelled", value: snapshot.cancelled, tone: "default" },
  ];

  const offPlan =
    snapshot.off_plan_makeup +
    snapshot.off_plan_ad_hoc +
    snapshot.off_plan_merged;

  return (
    <Card size="sm">
      <CardContent>
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
          {tiles.map((t) => (
            <div key={t.label} className="flex flex-col">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">
                {t.label}
              </span>
              <span className={`text-2xl font-semibold ${TONE_CLASS[t.tone]}`}>
                {t.value}
              </span>
            </div>
          ))}
        </div>
        {offPlan > 0 && (
          <p className="mt-3 text-xs text-muted-foreground">
            +{offPlan} off-plan today: {snapshot.off_plan_makeup} makeup ·{" "}
            {snapshot.off_plan_ad_hoc} ad-hoc · {snapshot.off_plan_merged}{" "}
            merged
          </p>
        )}
      </CardContent>
    </Card>
  );
}
