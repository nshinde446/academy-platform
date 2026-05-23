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
import type { StudentResponse } from "../_schemas/student";

interface StudentTableProps {
  students: StudentResponse[];
  onEdit: (student: StudentResponse) => void;
  onDelete: (student: StudentResponse) => void;
}

export function StudentTable({ students, onEdit, onDelete }: StudentTableProps) {
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead className="hidden sm:table-cell">Class</TableHead>
            <TableHead className="hidden sm:table-cell">Target</TableHead>
            <TableHead className="hidden md:table-cell">Roll No</TableHead>
            <TableHead className="hidden xl:table-cell">Gender</TableHead>
            <TableHead className="hidden lg:table-cell">Email</TableHead>
            <TableHead className="hidden lg:table-cell">Phone</TableHead>
            <TableHead className="hidden xl:table-cell">Parent Mobile</TableHead>
            <TableHead className="hidden xl:table-cell">RFID</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {students.map((s) => (
            <TableRow key={s.id}>
              <TableCell className="font-medium">
                {s.first_name} {s.last_name}
              </TableCell>
              <TableCell className="hidden sm:table-cell">
                {s.standard
                  ? s.standard === "Dropper"
                    ? "Dropper"
                    : `Class ${s.standard}`
                  : "—"}
              </TableCell>
              <TableCell className="hidden sm:table-cell">
                {s.target_exam ? (
                  <Badge variant="secondary">{s.target_exam}</Badge>
                ) : (
                  "—"
                )}
              </TableCell>
              <TableCell className="hidden md:table-cell">
                {s.enrollment_number ?? "—"}
              </TableCell>
              <TableCell className="hidden xl:table-cell">
                {s.gender ?? "—"}
              </TableCell>
              <TableCell className="hidden lg:table-cell">
                {s.email ?? "—"}
              </TableCell>
              <TableCell className="hidden lg:table-cell">
                {s.phone ?? "—"}
              </TableCell>
              <TableCell className="hidden xl:table-cell">
                {s.parent_mobile ?? "—"}
              </TableCell>
              <TableCell className="hidden xl:table-cell font-mono text-xs">
                {s.rfid_number ?? "—"}
              </TableCell>
              <TableCell>
                <Badge
                  variant={s.status === "active" ? "success" : "secondary"}
                >
                  {s.status}
                </Badge>
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-1">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => onEdit(s)}
                  >
                    Edit
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    onClick={() => onDelete(s)}
                    aria-label={`Delete ${s.first_name} ${s.last_name}`}
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
