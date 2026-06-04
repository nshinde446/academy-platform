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
import type {
  BatchSummary,
  LectureResponse,
  SubjectSummary,
  TeacherSummary,
  TopicSummary,
} from "../_schemas/lecture";

// The opt-in MSA view collapses the 7 backend statuses into the 4 the user
// thinks in: Scheduled / Live / Completed / No-show. Substitute is metadata,
// not a status — when a sub delivered, the row stays in its lifecycle state
// (most often "completed") with a "by substitute" sub-label.
export type MsaStatusGroup = "scheduled" | "live" | "completed" | "no_show";

export function groupStatus(s: LectureResponse["lecture_status"]): MsaStatusGroup | null {
  if (s === "scheduled" || s === "rescheduled") return "scheduled";
  if (s === "started" || s === "paused") return "live";
  if (s === "completed") return "completed";
  if (s === "no_show") return "no_show";
  // cancelled — intentional removal, hidden from the MSA view
  return null;
}

interface LectureTableMsaProps {
  lectures: LectureResponse[];
  batches: BatchSummary[];
  teachers: TeacherSummary[];
  subjects: SubjectSummary[];
  topics: TopicSummary[];
  onStart: (lecture: LectureResponse) => void;
  onComplete: (lecture: LectureResponse) => void;
  onGenerateDpp: (lecture: LectureResponse) => void;
  onRecordMakeup: (lecture: LectureResponse) => void;
}

function lookup<T extends { id: string }>(list: T[], id: string | null): T | undefined {
  if (!id) return undefined;
  return list.find((x) => x.id === id);
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const date = d.toLocaleDateString(undefined, { month: "short", day: "2-digit" });
  const time = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return `${date} · ${time}`;
}

function teacherName(t: TeacherSummary | undefined): string {
  if (!t) return "—";
  return [t.first_name, t.last_name].filter(Boolean).join(" ") || "—";
}

function batchTail(name: string | undefined): string {
  if (!name) return "—";
  const parts = name.trim().split(/\s+/);
  return parts.slice(-2).join(" ");
}

const STATUS_PILL: Record<
  MsaStatusGroup,
  { label: string; variant: "default" | "secondary" | "destructive" | "success" }
> = {
  scheduled: { label: "Scheduled", variant: "secondary" },
  live: { label: "Live", variant: "default" },
  completed: { label: "Completed", variant: "success" },
  no_show: { label: "No-show", variant: "destructive" },
};

export function LectureTableMsa({
  lectures,
  batches,
  teachers,
  subjects,
  topics,
  onStart,
  onComplete,
  onGenerateDpp,
  onRecordMakeup,
}: LectureTableMsaProps) {
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>When</TableHead>
            <TableHead>Teacher</TableHead>
            <TableHead className="hidden md:table-cell">Batch · Subject</TableHead>
            <TableHead className="hidden lg:table-cell">Topic</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Quick action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {lectures.map((l) => {
            const group = groupStatus(l.lecture_status);
            if (!group) return null;
            const batch = lookup(batches, l.batch_id);
            const teacher = lookup(teachers, l.teacher_id);
            const actualTeacher = lookup(teachers, l.actual_teacher_id);
            const subject = lookup(subjects, l.subject_id);
            const topic = lookup(topics, l.topic_id);
            const pill = STATUS_PILL[group];
            const hasSub = !!l.actual_teacher_id;
            const subLabel =
              group === "completed" && hasSub
                ? "by substitute"
                : group === "live" && hasSub
                  ? "with substitute"
                  : undefined;

            return (
              <TableRow key={l.id}>
                <TableCell className="text-xs tabular-nums whitespace-nowrap">
                  {formatWhen(l.scheduled_start)}
                </TableCell>
                <TableCell>
                  {actualTeacher ? (
                    <div className="flex flex-col">
                      <span className="line-through text-muted-foreground text-xs">
                        {teacherName(teacher)}
                      </span>
                      <span className="font-medium">
                        {teacherName(actualTeacher)}
                      </span>
                    </div>
                  ) : (
                    <span className="font-medium">{teacherName(teacher)}</span>
                  )}
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  <div className="flex items-center gap-2 text-sm">
                    <Badge variant="outline">{subject?.name ?? "—"}</Badge>
                    <span className="text-xs text-muted-foreground">
                      {batchTail(batch?.name)}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                  {topic ? topic.name : "—"}
                </TableCell>
                <TableCell>
                  <div className="flex flex-col items-start gap-0.5">
                    <Badge variant={pill.variant}>{pill.label}</Badge>
                    {subLabel && (
                      <span className="text-[10px] text-muted-foreground">
                        {subLabel}
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  {group === "scheduled" && (
                    <Button
                      type="button"
                      size="xs"
                      variant="outline"
                      onClick={() => onStart(l)}
                      aria-label={`Start lecture ${l.id}`}
                    >
                      Start
                    </Button>
                  )}
                  {group === "live" && (
                    <Button
                      type="button"
                      size="xs"
                      variant="default"
                      onClick={() => onComplete(l)}
                      aria-label={`Complete lecture ${l.id}`}
                    >
                      Complete
                    </Button>
                  )}
                  {group === "completed" && (
                    <Button
                      type="button"
                      size="xs"
                      variant="outline"
                      onClick={() => onGenerateDpp(l)}
                      aria-label={`Generate DPP for lecture ${l.id}`}
                    >
                      ✦ Generate DPP
                    </Button>
                  )}
                  {group === "no_show" && (
                    <Button
                      type="button"
                      size="xs"
                      variant="ghost"
                      onClick={() => onRecordMakeup(l)}
                      aria-label={`Record makeup for lecture ${l.id}`}
                    >
                      Record makeup
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
