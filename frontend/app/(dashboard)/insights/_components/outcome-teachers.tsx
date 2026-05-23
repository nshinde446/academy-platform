"use client";

import Link from "next/link";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { OutcomeTeacherRow } from "../_schemas/adherence";

interface OutcomeTeachersProps {
  rows: OutcomeTeacherRow[];
  branchAvg: number;
}

function deltaVariant(
  delta: number,
): "success" | "default" | "secondary" | "destructive" {
  if (delta >= 5) return "success";
  if (delta >= -2) return "default";
  if (delta >= -10) return "secondary";
  return "destructive";
}

export function OutcomeTeachers({ rows, branchAvg }: OutcomeTeachersProps) {
  if (rows.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">
        No teacher × subject pairs with a completed lecture AND a published
        test in this window yet.
      </p>
    );
  }

  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Teacher</TableHead>
            <TableHead>Subject</TableHead>
            <TableHead className="text-right">Tests</TableHead>
            <TableHead className="text-right">Students</TableHead>
            <TableHead className="text-right">Avg score</TableHead>
            <TableHead className="text-right">
              vs. branch {branchAvg.toFixed(1)}%
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={`${r.teacher_id}-${r.subject_id}`}>
              <TableCell className="font-medium">
                <Link
                  href={`/teachers/${r.teacher_id}`}
                  className="hover:underline"
                >
                  {r.first_name} {r.last_name}
                </Link>
              </TableCell>
              <TableCell>{r.subject_name}</TableCell>
              <TableCell className="text-right">{r.tests_count}</TableCell>
              <TableCell className="text-right">{r.students_count}</TableCell>
              <TableCell className="text-right tabular-nums">
                {r.avg_score_pct.toFixed(1)}%
              </TableCell>
              <TableCell className="text-right">
                <Badge variant={deltaVariant(r.delta_vs_branch_pct)}>
                  {r.delta_vs_branch_pct >= 0 ? "+" : ""}
                  {r.delta_vs_branch_pct.toFixed(1)}pp
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
