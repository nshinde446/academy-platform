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
import type { CourseResponse } from "../_schemas/course";

interface CourseTableProps {
  courses: CourseResponse[];
  onEdit: (course: CourseResponse) => void;
  onDelete: (course: CourseResponse) => void;
  // Row selection for bulk delete — optional; when omitted the checkbox
  // column is hidden.
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
  onToggleSelectAll?: () => void;
}

export function CourseTable({
  courses,
  onEdit,
  onDelete,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
}: CourseTableProps) {
  const selectable = !!onToggleSelect;
  const allSelected =
    selectable && courses.length > 0 && courses.every((c) => selectedIds?.has(c.id));
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            {selectable && (
              <TableHead className="w-9">
                <input
                  type="checkbox"
                  aria-label="Select all courses"
                  checked={allSelected}
                  onChange={() => onToggleSelectAll?.()}
                />
              </TableHead>
            )}
            <TableHead>Name</TableHead>
            <TableHead>Code</TableHead>
            <TableHead className="hidden sm:table-cell">Duration</TableHead>
            <TableHead className="hidden md:table-cell">Description</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {courses.map((c) => (
            <TableRow key={c.id}>
              {selectable && (
                <TableCell>
                  <input
                    type="checkbox"
                    aria-label={`Select course ${c.name}`}
                    checked={selectedIds?.has(c.id) ?? false}
                    onChange={() => onToggleSelect?.(c.id)}
                  />
                </TableCell>
              )}
              <TableCell className="font-medium">{c.name}</TableCell>
              <TableCell>{c.code}</TableCell>
              <TableCell className="hidden sm:table-cell">
                {c.duration_years} {c.duration_years === 1 ? "year" : "years"}
              </TableCell>
              <TableCell className="hidden md:table-cell text-muted-foreground">
                {c.description || "—"}
              </TableCell>
              <TableCell>
                <Badge
                  variant={c.status === "active" ? "success" : "secondary"}
                >
                  {c.status}
                </Badge>
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-1">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => onEdit(c)}
                  >
                    Edit
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    onClick={() => onDelete(c)}
                    aria-label={`Delete course ${c.name}`}
                  >
                    Delete
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
