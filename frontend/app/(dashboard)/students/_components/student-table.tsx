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
import { Button } from "@/components/ui/button";
import {
  FeesBadge,
  NumCell,
  RosterAvatar,
  ScoreCell,
} from "@/components/roster/roster-primitives";
import type { StudentResponse, StudentWithStats } from "../_schemas/student";

interface StudentTableProps {
  rows: StudentWithStats[];
  // Index by id so the Edit/Delete handlers can resolve the full
  // StudentResponse (which carries fields the stats payload omits).
  studentsById: Record<string, StudentResponse>;
  onEdit: (student: StudentResponse) => void;
  onDelete: (student: StudentResponse) => void;
}

export function StudentTable({
  rows,
  studentsById,
  onEdit,
  onDelete,
}: StudentTableProps) {
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-9"></TableHead>
            <TableHead>Name</TableHead>
            <TableHead className="hidden sm:table-cell">Class</TableHead>
            <TableHead className="hidden md:table-cell">Target</TableHead>
            <TableHead className="hidden lg:table-cell">Batch</TableHead>
            <TableHead className="text-right hidden md:table-cell">
              Rank
            </TableHead>
            <TableHead className="text-right">Avg score</TableHead>
            <TableHead className="text-right hidden sm:table-cell">
              Attendance
            </TableHead>
            <TableHead className="text-right hidden lg:table-cell">
              DPP
            </TableHead>
            <TableHead className="hidden md:table-cell">Fees</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => {
            const full = studentsById[r.id];
            return (
              <TableRow key={r.id}>
                <TableCell>
                  <RosterAvatar first={r.first_name} last={r.last_name} />
                </TableCell>
                <TableCell className="font-medium">
                  {r.first_name} {r.last_name}
                  {r.enrollment_number ? (
                    <span className="ml-2 text-xs text-muted-foreground tabular-nums">
                      {r.enrollment_number}
                    </span>
                  ) : null}
                </TableCell>
                <TableCell className="hidden sm:table-cell">
                  {r.standard
                    ? r.standard === "Dropper"
                      ? "Dropper"
                      : `Class ${r.standard}`
                    : "—"}
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  {r.target_exam ? (
                    <Badge variant="secondary">{r.target_exam}</Badge>
                  ) : (
                    "—"
                  )}
                </TableCell>
                <TableCell className="hidden lg:table-cell text-xs text-muted-foreground">
                  {r.batch_name ?? "—"}
                </TableCell>
                <TableCell className="text-right hidden md:table-cell">
                  {r.batch_rank ? (
                    <NumCell>#{r.batch_rank}</NumCell>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <ScoreCell value={r.avg_score_pct} />
                </TableCell>
                <TableCell className="text-right hidden sm:table-cell">
                  <NumCell>{r.attendance_pct.toFixed(0)}%</NumCell>
                </TableCell>
                <TableCell className="text-right hidden lg:table-cell">
                  <ScoreCell value={r.dpp_completion_pct} tone="muted" />
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  <FeesBadge status={r.fees_status} />
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={!full}
                      onClick={() => full && onEdit(full)}
                    >
                      Edit
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="destructive"
                      disabled={!full}
                      onClick={() => full && onDelete(full)}
                      aria-label={`Delete ${r.first_name} ${r.last_name}`}
                    >
                      Delete
                    </Button>
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
