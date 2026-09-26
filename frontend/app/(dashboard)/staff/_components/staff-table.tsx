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
import { FaceAvatar } from "@/components/roster/face-avatar";
import type { StaffResponse } from "../_schemas/staff";

interface StaffTableProps {
  rows: StaffResponse[];
  branchId?: string;
  onEdit: (staff: StaffResponse) => void;
  onDelete?: (staff: StaffResponse) => void;
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onToggleSelectAll: () => void;
}

export function StaffTable({
  rows,
  branchId,
  onEdit,
  onDelete,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
}: StaffTableProps) {
  const allSelected = rows.length > 0 && rows.every((r) => selectedIds.has(r.id));

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={onToggleSelectAll}
                aria-label="Select all staff"
              />
            </TableHead>
            <TableHead>Code</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Department</TableHead>
            <TableHead>Designation</TableHead>
            <TableHead>Teacher link</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((s) => (
            <TableRow key={s.id}>
              <TableCell>
                <input
                  type="checkbox"
                  checked={selectedIds.has(s.id)}
                  onChange={() => onToggleSelect(s.id)}
                  aria-label={`Select ${s.first_name}`}
                />
              </TableCell>
              <TableCell>
                <span className="font-mono">{s.emp_code}</span>
                {s.is_legacy_code && (
                  <Badge variant="warning" className="ml-2">
                    legacy
                  </Badge>
                )}
              </TableCell>
              <TableCell>
                <span className="inline-flex items-center gap-2">
                  <FaceAvatar
                    src={
                      branchId
                        ? `/api/v1/staff/${s.id}/photo?branch_id=${branchId}`
                        : null
                    }
                    first={s.first_name}
                    last={s.last_name ?? ""}
                  />
                  {[s.title, s.first_name, s.last_name]
                    .filter(Boolean)
                    .join(" ")}
                </span>
              </TableCell>
              <TableCell>{s.department_name ?? "—"}</TableCell>
              <TableCell>{s.designation ?? "—"}</TableCell>
              <TableCell>
                {s.linked_teacher_id ? (
                  <Badge variant="success">linked</Badge>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </TableCell>
              <TableCell className="text-right">
                <Button variant="ghost" size="sm" onClick={() => onEdit(s)}>
                  Edit
                </Button>
                {onDelete && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive"
                    onClick={() => onDelete(s)}
                  >
                    Delete
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
