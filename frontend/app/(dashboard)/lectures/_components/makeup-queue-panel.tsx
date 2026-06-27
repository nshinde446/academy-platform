"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type {
  BatchSummary,
  LectureResponse,
  SubjectSummary,
  TeacherSummary,
} from "../_schemas/lecture";

interface MakeupQueuePanelProps {
  lectures: LectureResponse[];
  batches: BatchSummary[];
  teachers: TeacherSummary[];
  subjects: SubjectSummary[];
  onRecordMakeup: (lecture: LectureResponse) => void;
}

function name<T extends { id: string }>(
  list: T[],
  id: string | null,
  render: (x: T) => string,
): string {
  if (!id) return "—";
  const found = list.find((x) => x.id === id);
  return found ? render(found) : "—";
}

function whenLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function missLabel(l: LectureResponse): string {
  if (l.lecture_status === "cancelled") return "cancelled";
  const reason = (l.no_show_reason ?? "").toLowerCase();
  if (reason === "teacher_no_show") return "no-show · teacher";
  if (reason === "student_no_show") return "no-show · students";
  return "no-show";
}

/** Makeup queue: cancelled / no-show lectures not yet made up. Surfaces the
 * missed topics so they're rescheduled, not silently dropped. Each row opens
 * the Record Makeup flow prefilled with the missed lecture. */
export function MakeupQueuePanel({
  lectures,
  batches,
  teachers,
  subjects,
  onRecordMakeup,
}: MakeupQueuePanelProps) {
  if (lectures.length === 0) return null;

  return (
    <Card
      size="sm"
      className="border-rose-500/40 bg-rose-500/5"
      data-testid="makeup-queue-panel"
    >
      <div className="flex flex-col gap-2 px-3 py-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">
            {lectures.length} lecture{lectures.length !== 1 ? "s" : ""} need
            {lectures.length === 1 ? "s" : ""} a makeup
          </span>
          <span className="text-xs text-muted-foreground">
            · cancelled or no-show, not yet rescheduled
          </span>
        </div>
        <div className="divide-y divide-border/60 rounded-lg border bg-background">
          {lectures.map((l) => (
            <div
              key={l.id}
              className="flex items-center gap-3 px-3 py-2 text-sm"
            >
              <span className="w-40 shrink-0 tabular-nums text-muted-foreground">
                {whenLabel(l.scheduled_start)}
              </span>
              <span className="min-w-0 flex-1 truncate">
                <span className="font-medium">
                  {name(batches, l.batch_id, (b) => b.name)}
                </span>
                {" · "}
                {name(subjects, l.subject_id, (s) => s.name)}
                {" · "}
                {name(
                  teachers,
                  l.teacher_id,
                  (t) => `${t.first_name} ${t.last_name}`.trim(),
                )}
              </span>
              <Badge variant="secondary" className="shrink-0 text-[10px]">
                {missLabel(l)}
              </Badge>
              <Button
                type="button"
                size="sm"
                onClick={() => onRecordMakeup(l)}
                aria-label={`Record makeup for lecture ${l.id}`}
                className="shrink-0"
              >
                Record Makeup
              </Button>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
