"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { OutcomeAttendanceBucket } from "../_schemas/adherence";

interface OutcomeBucketsProps {
  buckets: OutcomeAttendanceBucket[];
}

function barTone(score: number): string {
  if (score >= 75) return "bg-emerald-500";
  if (score >= 60) return "bg-primary";
  if (score >= 45) return "bg-amber-500";
  return "bg-destructive";
}

export function OutcomeBuckets({ buckets }: OutcomeBucketsProps) {
  const totalStudents = buckets.reduce((s, b) => s + b.students, 0);
  if (totalStudents === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">
        No attendance-and-score data yet — students need to have attended
        lectures and taken tests in this window.
      </p>
    );
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">
          Attendance × test score
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3">
          {buckets.map((b) => {
            const widthPct = Math.min(b.avg_score, 100);
            return (
              <div key={b.bucket} className="flex flex-col gap-1">
                <div className="flex items-baseline justify-between text-sm">
                  <span className="font-medium tabular-nums">
                    Attendance {b.bucket}
                  </span>
                  <span className="text-muted-foreground text-xs">
                    {b.students} student{b.students !== 1 ? "s" : ""}
                    {b.students > 0 && (
                      <>
                        {" · "}
                        <span className="font-medium text-foreground tabular-nums">
                          {b.avg_score.toFixed(1)}%
                        </span>{" "}
                        avg score
                      </>
                    )}
                  </span>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className={`h-full transition-all ${barTone(b.avg_score)}`}
                    style={{ width: `${widthPct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Does showing up correlate with scoring? A larger gap between the
          top and bottom row is stronger evidence that attendance matters.
        </p>
      </CardContent>
    </Card>
  );
}
