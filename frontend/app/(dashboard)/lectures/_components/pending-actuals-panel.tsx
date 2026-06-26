"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type {
  BatchSummary,
  LectureResponse,
  SubjectSummary,
  TeacherSummary,
} from "../_schemas/lecture";

interface PendingActualsPanelProps {
  lectures: LectureResponse[];
  batches: BatchSummary[];
  teachers: TeacherSummary[];
  subjects: SubjectSummary[];
  onActuals: (lecture: LectureResponse) => void;
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

/** End-of-day worklist: past lectures that were never closed out. Surfaces them
 * so nothing silently slips through; each opens the End-of-Day dialog. */
export function PendingActualsPanel({
  lectures,
  batches,
  teachers,
  subjects,
  onActuals,
}: PendingActualsPanelProps) {
  if (lectures.length === 0) return null;

  return (
    <Card
      size="sm"
      className="border-amber-500/40 bg-amber-500/5"
      data-testid="pending-actuals-panel"
    >
      <div className="flex flex-col gap-2 px-3 py-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">
            {lectures.length} lecture{lectures.length !== 1 ? "s" : ""} need
            {lectures.length === 1 ? "s" : ""} an end-of-day update
          </span>
          <span className="text-xs text-muted-foreground">
            · already past, not yet closed out
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
              <Button
                type="button"
                size="sm"
                onClick={() => onActuals(l)}
                aria-label={`Record end-of-day actuals for lecture ${l.id}`}
                className="shrink-0"
              >
                End of Day
              </Button>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
