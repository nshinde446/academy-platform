"use client";

import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import type { SyllabusBatchRow } from "../_schemas/adherence";

interface SyllabusCoverageProps {
  rows: SyllabusBatchRow[];
}

function barTone(pct: number): string {
  if (pct >= 75) return "bg-emerald-500";
  if (pct >= 50) return "bg-primary";
  if (pct >= 25) return "bg-amber-500";
  return "bg-destructive";
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
            <TableHead className="text-right">Total topics</TableHead>
            <TableHead className="w-1/3">Coverage</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.batch_id}>
              <TableCell>
                <div className="flex flex-col">
                  <span className="font-medium">{r.batch_name}</span>
                  <span className="text-xs text-muted-foreground">
                    {r.batch_code}
                  </span>
                </div>
              </TableCell>
              <TableCell className="text-right">{r.delivered_topics}</TableCell>
              <TableCell className="text-right">{r.total_topics}</TableCell>
              <TableCell>
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className={`h-full transition-all ${barTone(r.coverage_pct)}`}
                      style={{ width: `${Math.min(r.coverage_pct, 100)}%` }}
                    />
                  </div>
                  <span className="text-xs tabular-nums w-12 text-right">
                    {r.coverage_pct.toFixed(1)}%
                  </span>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
