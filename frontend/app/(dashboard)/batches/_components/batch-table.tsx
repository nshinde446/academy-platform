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
import type {
  AcademicYearResponse,
  BatchResponse,
  CourseResponse,
} from "../_schemas/batch";

interface BatchTableProps {
  batches: BatchResponse[];
  courses: CourseResponse[];
  academicYears: AcademicYearResponse[];
  onEdit: (batch: BatchResponse) => void;
  onDelete: (batch: BatchResponse) => void;
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
  onToggleSelectAll?: () => void;
}

function findName<T extends { id: string; name: string }>(
  list: T[],
  id: string
): string {
  return list.find((x) => x.id === id)?.name ?? "—";
}

export function BatchTable({
  batches,
  courses,
  academicYears,
  onEdit,
  onDelete,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
}: BatchTableProps) {
  const selectable = !!onToggleSelect;
  const allSelected =
    selectable && batches.length > 0 && batches.every((b) => selectedIds?.has(b.id));
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            {selectable && (
              <TableHead className="w-9">
                <input
                  type="checkbox"
                  aria-label="Select all batches"
                  checked={allSelected}
                  onChange={() => onToggleSelectAll?.()}
                />
              </TableHead>
            )}
            <TableHead>Name</TableHead>
            <TableHead className="hidden sm:table-cell">Course</TableHead>
            <TableHead className="hidden md:table-cell">Duration</TableHead>
            <TableHead className="hidden lg:table-cell">
              Academic Years
            </TableHead>
            <TableHead className="hidden xl:table-cell">Capacity</TableHead>
            <TableHead className="hidden lg:table-cell">Exam date</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {batches.map((b) => {
            const startName = findName(academicYears, b.start_academic_year_id);
            const endName = findName(academicYears, b.end_academic_year_id);
            const range =
              startName === endName ? startName : `${startName} → ${endName}`;
            return (
              <TableRow key={b.id}>
                {selectable && (
                  <TableCell>
                    <input
                      type="checkbox"
                      aria-label={`Select batch ${b.name}`}
                      checked={selectedIds?.has(b.id) ?? false}
                      onChange={() => onToggleSelect?.(b.id)}
                    />
                  </TableCell>
                )}
                <TableCell className="font-medium">{b.name}</TableCell>
                <TableCell className="hidden sm:table-cell">
                  {findName(courses, b.course_id)}
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  {b.duration_years}{" "}
                  {b.duration_years === 1 ? "year" : "years"}
                </TableCell>
                <TableCell className="hidden lg:table-cell">{range}</TableCell>
                <TableCell className="hidden xl:table-cell">
                  {b.capacity}
                </TableCell>
                <TableCell className="hidden lg:table-cell text-xs text-muted-foreground">
                  {b.target_exam_date
                    ? new Date(b.target_exam_date).toLocaleDateString(
                        undefined,
                        { month: "short", day: "2-digit", year: "numeric" },
                      )
                    : "—"}
                </TableCell>
                <TableCell>
                  <Badge
                    variant={b.status === "active" ? "success" : "secondary"}
                  >
                    {b.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => onEdit(b)}
                    >
                      Edit
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="destructive"
                      onClick={() => onDelete(b)}
                      aria-label={`Delete batch ${b.name}`}
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
