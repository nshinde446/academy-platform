"use client";

import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import type { ProductivitySummaryRow } from "../_schemas/productivity-report";

function fmtHours(min: number): string {
  const h = Math.floor((min || 0) / 60);
  const m = (min || 0) % 60;
  return `${h} Hours ${m} Mins`;
}

// The Daily Summary Report table (client document, Section 3): one row per
// teacher — Sr No, Employee Code, Initials, Teacher, Subject, Present Days,
// Total Lectures, Scheduled + Delivered hours.
export function ReportTable({ rows }: { rows: ProductivitySummaryRow[] }) {
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table stickyHeader containerClassName="max-h-[70vh]">
        <TableHeader>
          <TableRow>
            <TableHead className="w-12 text-right">Sr No</TableHead>
            <TableHead>Employee Code</TableHead>
            <TableHead>Initials</TableHead>
            <TableHead>Teacher</TableHead>
            <TableHead>Subject</TableHead>
            <TableHead className="text-right">Present Days</TableHead>
            <TableHead className="text-right">Total Lectures</TableHead>
            <TableHead className="text-right hidden sm:table-cell">
              Scheduled Hours
            </TableHead>
            <TableHead className="text-right hidden sm:table-cell">
              Delivered Hours
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r, i) => (
            <TableRow key={`${r.emp_code}-${i}`}>
              <TableCell className="text-right tabular-nums text-muted-foreground">
                {i + 1}
              </TableCell>
              <TableCell className="font-mono text-sm">{r.emp_code}</TableCell>
              <TableCell className="font-semibold">{r.initials}</TableCell>
              <TableCell className="font-medium">{r.teacher_name}</TableCell>
              <TableCell>{r.subject}</TableCell>
              <TableCell className="text-right tabular-nums">
                {r.present_days}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {r.total_lectures}
              </TableCell>
              <TableCell className="text-right tabular-nums hidden sm:table-cell text-muted-foreground">
                {fmtHours(r.scheduled_minutes)}
              </TableCell>
              <TableCell className="text-right tabular-nums hidden sm:table-cell">
                {fmtHours(r.delivered_minutes)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
