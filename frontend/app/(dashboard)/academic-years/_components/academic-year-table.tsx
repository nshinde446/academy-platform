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
import type { AcademicYearResponse } from "../_schemas/academic-year";

interface AcademicYearTableProps {
  academicYears: AcademicYearResponse[];
  onDelete: (year: AcademicYearResponse) => void;
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
  onToggleSelectAll?: () => void;
}

const IMMUTABLE_TITLE =
  "Academic years cannot be edited as they define immutable ranges.";

export function AcademicYearTable({
  academicYears,
  onDelete,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
}: AcademicYearTableProps) {
  const selectable = !!onToggleSelect;
  const allSelected =
    selectable &&
    academicYears.length > 0 &&
    academicYears.every((y) => selectedIds?.has(y.id));
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            {selectable && (
              <TableHead className="w-9">
                <input
                  type="checkbox"
                  aria-label="Select all academic years"
                  checked={allSelected}
                  onChange={() => onToggleSelectAll?.()}
                />
              </TableHead>
            )}
            <TableHead>Name</TableHead>
            <TableHead>Start</TableHead>
            <TableHead>End</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {academicYears.map((y) => (
            <TableRow key={y.id} title={IMMUTABLE_TITLE}>
              {selectable && (
                <TableCell>
                  <input
                    type="checkbox"
                    aria-label={`Select academic year ${y.name}`}
                    checked={selectedIds?.has(y.id) ?? false}
                    onChange={() => onToggleSelect?.(y.id)}
                  />
                </TableCell>
              )}
              <TableCell className="font-medium">{y.name}</TableCell>
              <TableCell>{y.start_year}</TableCell>
              <TableCell>{y.end_year}</TableCell>
              <TableCell>
                <Badge
                  variant={y.status === "active" ? "success" : "secondary"}
                >
                  {y.status}
                </Badge>
              </TableCell>
              <TableCell className="text-right">
                <Button
                  type="button"
                  size="sm"
                  variant="destructive"
                  onClick={() => onDelete(y)}
                  aria-label={`Delete academic year ${y.name}`}
                >
                  Delete
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
