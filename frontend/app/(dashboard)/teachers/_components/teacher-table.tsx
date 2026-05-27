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
  NumCell,
  RosterAvatar,
  ScoreCell,
} from "@/components/roster/roster-primitives";
import type { TeacherResponse, TeacherWithStats } from "../_schemas/teacher";

interface TeacherTableProps {
  rows: TeacherWithStats[];
  // Resolve Edit/Delete clicks back to the full TeacherResponse the
  // dialogs need.
  teachersById: Record<string, TeacherResponse>;
  onEdit: (teacher: TeacherResponse) => void;
  onDelete: (teacher: TeacherResponse) => void;
}

export function TeacherTable({
  rows,
  teachersById,
  onEdit,
  onDelete,
}: TeacherTableProps) {
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-9"></TableHead>
            <TableHead>Name</TableHead>
            <TableHead className="hidden md:table-cell">Subject</TableHead>
            <TableHead className="hidden lg:table-cell">Qualification</TableHead>
            <TableHead className="text-right hidden sm:table-cell">
              Years
            </TableHead>
            <TableHead className="text-right">Lectures (30d)</TableHead>
            <TableHead className="text-right hidden md:table-cell">
              Sub rate
            </TableHead>
            <TableHead className="text-right hidden lg:table-cell">
              Avg outcome
            </TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => {
            const full = teachersById[r.id];
            return (
              <TableRow key={r.id}>
                <TableCell>
                  <RosterAvatar first={r.first_name} last={r.last_name} />
                </TableCell>
                <TableCell className="font-medium">
                  {r.first_name} {r.last_name}
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  {r.subject_name ? (
                    <Badge variant="secondary">{r.subject_name}</Badge>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="hidden lg:table-cell text-xs text-muted-foreground">
                  {r.qualification ?? "—"}
                </TableCell>
                <TableCell className="text-right hidden sm:table-cell">
                  {r.years_experience != null ? (
                    <NumCell>{r.years_experience}</NumCell>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <NumCell>{r.lectures_30d}</NumCell>
                </TableCell>
                <TableCell className="text-right hidden md:table-cell">
                  <NumCell
                    className={
                      r.sub_rate_pct >= 25 ? "text-destructive" : undefined
                    }
                  >
                    {r.sub_rate_pct.toFixed(0)}%
                  </NumCell>
                </TableCell>
                <TableCell className="text-right hidden lg:table-cell">
                  {r.avg_outcome_delta_pp != null ? (
                    <ScoreCell value={r.avg_outcome_delta_pp} tone="muted" />
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
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
