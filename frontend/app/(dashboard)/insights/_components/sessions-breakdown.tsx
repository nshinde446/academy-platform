"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AdherenceSessions } from "../_schemas/adherence";

interface SessionsBreakdownProps {
  sessions: AdherenceSessions;
}

const ROWS: { key: keyof AdherenceSessions; label: string; hint: string }[] = [
  {
    key: "planned",
    label: "Planned (linked)",
    hint: "Sessions tied to one scheduled lecture",
  },
  {
    key: "makeup",
    label: "Makeup",
    hint: "Recorded against a cancelled / missed plan",
  },
  {
    key: "ad_hoc",
    label: "Ad-hoc",
    hint: "Unplanned classes with no original schedule",
  },
  {
    key: "merged",
    label: "Merged",
    hint: "One session covering 2+ scheduled lectures",
  },
];

export function SessionsBreakdown({ sessions }: SessionsBreakdownProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Recorded sessions</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {ROWS.map((r) => (
            <div key={r.key} className="flex flex-col">
              <dt className="text-xs text-muted-foreground">{r.label}</dt>
              <dd className="text-2xl font-semibold">{sessions[r.key]}</dd>
              <p className="text-xs text-muted-foreground mt-0.5">{r.hint}</p>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
