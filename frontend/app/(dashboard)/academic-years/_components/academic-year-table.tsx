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
import type { AcademicYearResponse } from "../_schemas/academic-year";

interface AcademicYearTableProps {
  academicYears: AcademicYearResponse[];
}

export function AcademicYearTable({ academicYears }: AcademicYearTableProps) {
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Start</TableHead>
            <TableHead>End</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {academicYears.map((y) => (
            <TableRow key={y.id}>
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
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
