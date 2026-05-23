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
import type {
  BatchSummary,
  LectureSessionResponse,
  SubjectSummary,
  TeacherSummary,
} from "../_schemas/lecture";

interface SessionListProps {
  sessions: LectureSessionResponse[];
  batches: BatchSummary[];
  teachers: TeacherSummary[];
  subjects: SubjectSummary[];
}

const ORIGIN_VARIANTS: Record<
  string,
  "default" | "secondary" | "success" | "destructive"
> = {
  planned: "secondary",
  makeup: "success",
  ad_hoc: "default",
};

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function SessionList({
  sessions,
  batches,
  teachers,
  subjects,
}: SessionListProps) {
  if (sessions.length === 0) return null;

  return (
    <div className="flex flex-col gap-3">
      <div>
        <h3 className="text-lg font-semibold">Recorded sessions</h3>
        <p className="text-sm text-muted-foreground">
          Actual teaching events — makeup classes and ad-hoc sessions that
          happened outside the schedule.
        </p>
      </div>
      <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>When</TableHead>
              <TableHead>Teacher</TableHead>
              <TableHead className="hidden sm:table-cell">Subject</TableHead>
              <TableHead className="hidden md:table-cell">Batches</TableHead>
              <TableHead>Origin</TableHead>
              <TableHead className="hidden lg:table-cell">Notes</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sessions.map((s) => {
              const t = teachers.find((x) => x.id === s.teacher_id);
              const subj = subjects.find((x) => x.id === s.subject_id);
              const batchNames = s.batch_ids
                .map((bid) => batches.find((b) => b.id === bid)?.name ?? "?")
                .join(", ");
              return (
                <TableRow key={s.id}>
                  <TableCell className="whitespace-nowrap">
                    {formatDateTime(s.actual_start)}
                  </TableCell>
                  <TableCell>
                    {t ? `${t.first_name} ${t.last_name}` : "—"}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    {subj?.name ?? "—"}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {batchNames || "—"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={ORIGIN_VARIANTS[s.origin] ?? "default"}>
                      {s.origin}
                    </Badge>
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-muted-foreground text-xs max-w-xs truncate">
                    {s.notes ?? "—"}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
