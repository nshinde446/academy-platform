"use client";

import Link from "next/link";
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
import type {
  BatchSummary,
  LectureResponse,
  LectureStatus,
  SubjectSummary,
  TeacherSummary,
  TopicSummary,
} from "../_schemas/lecture";

interface LectureTableProps {
  lectures: LectureResponse[];
  batches: BatchSummary[];
  teachers: TeacherSummary[];
  subjects: SubjectSummary[];
  topics: TopicSummary[];
  onStart: (lecture: LectureResponse) => void;
  onComplete: (lecture: LectureResponse) => void;
  onCancel: (lecture: LectureResponse) => void;
  onDelete: (lecture: LectureResponse) => void;
  onSubstitute: (lecture: LectureResponse) => void;
}

const STATUS_VARIANTS: Record<
  LectureStatus,
  "success" | "secondary" | "default" | "destructive"
> = {
  scheduled: "default",
  started: "success",
  paused: "secondary",
  completed: "secondary",
  cancelled: "destructive",
  rescheduled: "default",
};

function lookup<T extends { id: string }>(list: T[], id: string | null): T | undefined {
  if (!id) return undefined;
  return list.find((x) => x.id === id);
}

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

function teacherName(t: TeacherSummary | undefined): string {
  if (!t) return "—";
  return [t.first_name, t.last_name].filter(Boolean).join(" ") || "—";
}

export function LectureTable({
  lectures,
  batches,
  teachers,
  subjects,
  topics,
  onStart,
  onComplete,
  onCancel,
  onDelete,
  onSubstitute,
}: LectureTableProps) {
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Batch</TableHead>
            <TableHead className="hidden sm:table-cell">Teacher</TableHead>
            <TableHead className="hidden md:table-cell">Subject</TableHead>
            <TableHead className="hidden lg:table-cell">Topic</TableHead>
            <TableHead>Scheduled Start</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {lectures.map((l) => {
            const batch = lookup(batches, l.batch_id);
            const teacher = lookup(teachers, l.teacher_id);
            const actualTeacher = lookup(teachers, l.actual_teacher_id);
            const subject = lookup(subjects, l.subject_id);
            const topic = lookup(topics, l.topic_id);
            const canStart = l.lecture_status === "scheduled";
            const canComplete =
              l.lecture_status === "started" || l.lecture_status === "paused";
            const canCancel =
              l.lecture_status === "scheduled" ||
              l.lecture_status === "started" ||
              l.lecture_status === "paused";
            const canSubstitute = l.lecture_status !== "cancelled";

            return (
              <TableRow key={l.id}>
                <TableCell className="font-medium">
                  {batch ? batch.name : "—"}
                </TableCell>
                <TableCell className="hidden sm:table-cell">
                  {actualTeacher ? (
                    <div className="flex flex-col">
                      <span className="line-through text-muted-foreground text-xs">
                        {teacherName(teacher)}
                      </span>
                      <span className="font-medium">
                        {teacherName(actualTeacher)}
                      </span>
                      <Badge variant="secondary" className="w-fit mt-0.5 text-[10px]">
                        {l.change_reason ?? "substitute"}
                      </Badge>
                    </div>
                  ) : (
                    teacherName(teacher)
                  )}
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  {subject ? subject.name : "—"}
                </TableCell>
                <TableCell className="hidden lg:table-cell text-muted-foreground">
                  {topic ? topic.name : "—"}
                </TableCell>
                <TableCell>{formatDateTime(l.scheduled_start)}</TableCell>
                <TableCell>
                  <Badge variant={STATUS_VARIANTS[l.lecture_status]}>
                    {l.lecture_status}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex flex-wrap justify-end gap-1">
                    {canStart && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onStart(l)}
                        aria-label={`Start lecture ${l.id}`}
                      >
                        Start
                      </Button>
                    )}
                    {canComplete && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onComplete(l)}
                        aria-label={`Complete lecture ${l.id}`}
                      >
                        Complete
                      </Button>
                    )}
                    {canCancel && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onCancel(l)}
                        aria-label={`Cancel lecture ${l.id}`}
                      >
                        Cancel
                      </Button>
                    )}
                    {canSubstitute && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onSubstitute(l)}
                        aria-label={`Mark substitute for lecture ${l.id}`}
                      >
                        {l.actual_teacher_id ? "Edit Sub" : "Substitute"}
                      </Button>
                    )}
                    <Link
                      href={`/attendance?lecture_id=${l.id}`}
                      className="inline-flex h-8 items-center rounded-md border border-input bg-background px-3 text-xs font-medium hover:bg-accent"
                      aria-label={`View attendance for lecture ${l.id}`}
                    >
                      Attendance
                    </Link>
                    <Button
                      type="button"
                      size="sm"
                      variant="destructive"
                      onClick={() => onDelete(l)}
                      aria-label={`Delete lecture ${l.id}`}
                    >
                      Delete
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
