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
import type { TeacherResponse } from "../_schemas/teacher";

interface TeacherTableProps {
  teachers: TeacherResponse[];
  onEdit: (teacher: TeacherResponse) => void;
  onDelete: (teacher: TeacherResponse) => void;
}

export function TeacherTable({ teachers, onEdit, onDelete }: TeacherTableProps) {
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead className="hidden lg:table-cell">Email</TableHead>
            <TableHead className="hidden md:table-cell">Phone</TableHead>
            <TableHead className="hidden lg:table-cell">Qualification</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {teachers.map((t) => (
            <TableRow key={t.id}>
              <TableCell className="font-medium">
                {t.first_name} {t.last_name}
              </TableCell>
              <TableCell className="hidden lg:table-cell">
                {t.email ?? "—"}
              </TableCell>
              <TableCell className="hidden md:table-cell">
                {t.phone ?? "—"}
              </TableCell>
              <TableCell className="hidden lg:table-cell">
                {t.qualification ?? "—"}
              </TableCell>
              <TableCell>
                <Badge
                  variant={t.status === "active" ? "success" : "secondary"}
                >
                  {t.status}
                </Badge>
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-1">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => onEdit(t)}
                  >
                    Edit
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    onClick={() => onDelete(t)}
                    aria-label={`Delete ${t.first_name} ${t.last_name}`}
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
