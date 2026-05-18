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
import type { CourseResponse } from "../_schemas/course";

interface CourseTableProps {
  courses: CourseResponse[];
}

export function CourseTable({ courses }: CourseTableProps) {
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Code</TableHead>
            <TableHead className="hidden sm:table-cell">Duration</TableHead>
            <TableHead className="hidden md:table-cell">Description</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {courses.map((c) => (
            <TableRow key={c.id}>
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
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
