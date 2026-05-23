"use client";

import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { PaceStatus, SyllabusBatchRow } from "../_schemas/adherence";

interface SyllabusCoverageProps {
  rows: SyllabusBatchRow[];
}

function barTone(pct: number): string {
  if (pct >= 75) return "bg-emerald-500";
  if (pct >= 50) return "bg-primary";
  if (pct >= 25) return "bg-amber-500";
  return "bg-destructive";
}

const PACE_LABEL: Record<PaceStatus, string> = {
  ahead: "ahead",
  on_pace: "on pace",
  behind: "behind",
  critically_behind: "critical",
  no_data: "no target",
};

function paceVariant(
  status: PaceStatus,
): "success" | "default" | "secondary" | "destructive" {
  switch (status) {
    case "ahead":
      return "success";
    case "on_pace":
      return "success";
    case "behind":
      return "default";
    case "critically_behind":
      return "destructive";
    default:
      return "secondary";
  }
}

export function SyllabusCoverage({ rows }: SyllabusCoverageProps) {
  if (rows.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">
        No batches yet — coverage will populate once batches and topics are set
        up.
      </p>
    );
  }

  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Batch</TableHead>
            <TableHead className="text-right">Delivered</TableHead>
            <TableHead className="text-right hidden sm:table-cell">
              Total
            </TableHead>
            <TableHead className="w-1/3">Coverage vs. expected</TableHead>
            <TableHead className="text-right">Pace</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => {
            const expectedLeft = Math.min(r.expected_coverage_pct, 100);
            const examDate = r.target_exam_date
              ? new Date(r.target_exam_date).toLocaleDateString(undefined, {
                  month: "short",
                  day: "2-digit",
                  year: "numeric",
                })
              : null;
            return (
              <TableRow key={r.batch_id}>
                <TableCell>
                  <div className="flex flex-col">
                    <span className="font-medium">{r.batch_name}</span>
                    <span className="text-xs text-muted-foreground">
                      {r.batch_code}
                      {examDate && <> · exam {examDate}</>}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  {r.delivered_topics}
                </TableCell>
                <TableCell className="text-right hidden sm:table-cell">
                  {r.total_topics}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <div className="relative flex-1 h-2 rounded-full bg-muted overflow-hidden">
                      {/* Delivered bar */}
                      <div
                        className={`absolute inset-y-0 left-0 ${barTone(r.coverage_pct)} transition-all`}
                        style={{
                          width: `${Math.min(r.coverage_pct, 100)}%`,
                        }}
                      />
                      {/* Expected marker — vertical line on the bar */}
                      {r.pace_status !== "no_data" && (
                        <div
                          className="absolute inset-y-0 w-px bg-foreground/70"
                          style={{ left: `${expectedLeft}%` }}
                          aria-label={`Expected ${r.expected_coverage_pct.toFixed(1)}%`}
                        />
                      )}
                    </div>
                    <span className="text-xs tabular-nums w-24 text-right">
                      {r.coverage_pct.toFixed(1)}%
                      {r.pace_status !== "no_data" && (
                        <span className="text-muted-foreground">
                          {" / "}
                          {r.expected_coverage_pct.toFixed(1)}%
                        </span>
                      )}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex flex-col items-end gap-0.5">
                    <Badge variant={paceVariant(r.pace_status)}>
                      {PACE_LABEL[r.pace_status]}
                    </Badge>
                    {r.pace_status !== "no_data" && (
                      <span className="text-[10px] text-muted-foreground tabular-nums">
                        {r.pace_delta_pct >= 0 ? "+" : ""}
                        {r.pace_delta_pct.toFixed(1)}pp
                      </span>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
