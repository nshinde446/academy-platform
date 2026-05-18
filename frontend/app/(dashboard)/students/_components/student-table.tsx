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
import type { StudentResponse } from "../_schemas/student";

interface StudentTableProps {
  students: StudentResponse[];
}

export function StudentTable({ students }: StudentTableProps) {
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead className="hidden sm:table-cell">Roll No</TableHead>
            <TableHead className="hidden lg:table-cell">Email</TableHead>
            <TableHead className="hidden md:table-cell">Phone</TableHead>
            <TableHead className="hidden md:table-cell">Parent Mobile</TableHead>
            <TableHead className="hidden lg:table-cell">RFID</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {students.map((s) => (
            <TableRow key={s.id}>
              <TableCell className="font-medium">
                {s.first_name} {s.last_name}
              </TableCell>
              <TableCell className="hidden sm:table-cell">
                {s.enrollment_number ?? "—"}
              </TableCell>
              <TableCell className="hidden lg:table-cell">
                {s.email ?? "—"}
              </TableCell>
              <TableCell className="hidden md:table-cell">
                {s.phone ?? "—"}
              </TableCell>
              <TableCell className="hidden md:table-cell">
                {s.parent_mobile ?? "—"}
              </TableCell>
              <TableCell className="hidden lg:table-cell font-mono text-xs">
                {s.rfid_number ?? "—"}
              </TableCell>
              <TableCell>
                <Badge
                  variant={s.status === "active" ? "success" : "secondary"}
                >
                  {s.status}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
