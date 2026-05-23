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
import type { AdherenceTeacherRow } from "../_schemas/adherence";

interface TeacherLeaderboardProps {
  rows: AdherenceTeacherRow[];
  limit?: number;
}

function rateTone(
  pct: number
): "success" | "default" | "destructive" | "secondary" {
  if (pct >= 30) return "destructive";
  if (pct >= 15) return "default";
  if (pct > 0) return "secondary";
  return "success";
}

export function TeacherLeaderboard({ rows, limit = 10 }: TeacherLeaderboardProps) {
  const top = rows.slice(0, limit);

  if (top.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">
        No lectures in the selected range — leaderboard will populate once
        teachers have scheduled lectures here.
      </p>
    );
  }

  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Teacher</TableHead>
            <TableHead className="text-right">Planned</TableHead>
            <TableHead className="text-right">Sub out</TableHead>
            <TableHead className="text-right">Sub in</TableHead>
            <TableHead className="text-right">Cancelled</TableHead>
            <TableHead className="text-right">Sub rate</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {top.map((r) => (
            <TableRow key={r.teacher_id}>
              <TableCell className="font-medium">
                {r.first_name} {r.last_name}
              </TableCell>
              <TableCell className="text-right">{r.planned}</TableCell>
              <TableCell className="text-right">{r.substituted_out}</TableCell>
              <TableCell className="text-right">{r.substituted_in}</TableCell>
              <TableCell className="text-right">{r.cancelled}</TableCell>
              <TableCell className="text-right">
                <Badge variant={rateTone(r.substitute_rate_pct)}>
                  {r.substitute_rate_pct.toFixed(1)}%
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
