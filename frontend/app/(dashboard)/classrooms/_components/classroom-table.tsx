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
import type { ClassroomResponse } from "../_schemas/classroom";

interface ClassroomTableProps {
  classrooms: ClassroomResponse[];
  onEdit: (c: ClassroomResponse) => void;
  onDelete: (c: ClassroomResponse) => void;
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
  onToggleSelectAll?: () => void;
}

export function ClassroomTable({
  classrooms,
  onEdit,
  onDelete,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
}: ClassroomTableProps) {
  const selectable = !!onToggleSelect;
  const allSelected =
    selectable && classrooms.length > 0 && classrooms.every((c) => selectedIds?.has(c.id));
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            {selectable && (
              <TableHead className="w-9">
                <input
                  type="checkbox"
                  aria-label="Select all classrooms"
                  checked={allSelected}
                  onChange={() => onToggleSelectAll?.()}
                />
              </TableHead>
            )}
            <TableHead>Name</TableHead>
            <TableHead>Code</TableHead>
            <TableHead className="hidden md:table-cell">Capacity</TableHead>
            <TableHead className="hidden md:table-cell">Floor</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {classrooms.map((c) => (
            <TableRow key={c.id}>
              {selectable && (
                <TableCell>
                  <input
                    type="checkbox"
                    aria-label={`Select classroom ${c.name}`}
                    checked={selectedIds?.has(c.id) ?? false}
                    onChange={() => onToggleSelect?.(c.id)}
                  />
                </TableCell>
              )}
              <TableCell className="font-medium">{c.name}</TableCell>
              <TableCell className="font-mono text-xs">{c.code}</TableCell>
              <TableCell className="hidden md:table-cell">
                {c.capacity}
              </TableCell>
              <TableCell className="hidden md:table-cell">
                {c.floor ?? "—"}
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
                    aria-label={`Delete ${c.name}`}
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
