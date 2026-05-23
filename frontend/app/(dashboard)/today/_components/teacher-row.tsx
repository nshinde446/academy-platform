"use client";

import { EventPill } from "./event-pill";
import type { RosterEvent, RosterTeacherRow } from "../_schemas/roster";

interface TeacherRowProps {
  teacher: RosterTeacherRow;
  onEventClick?: (event: RosterEvent) => void;
}

function priorityIcon(s: RosterTeacherRow["summary"]): string {
  if (s.no_show > 0) return "▲"; // problems → top
  if (s.in_progress > 0) return "●"; // live
  return "◐"; // upcoming / mixed
}

function priorityTone(s: RosterTeacherRow["summary"]): string {
  if (s.no_show > 0) return "text-destructive";
  if (s.in_progress > 0) return "text-emerald-600 dark:text-emerald-400";
  return "text-muted-foreground";
}

export function TeacherRow({ teacher, onEventClick }: TeacherRowProps) {
  const s = teacher.summary;
  const summaryParts = [
    s.planned > 0 ? `${s.planned} planned` : null,
    s.completed > 0 ? `${s.completed} done` : null,
    s.in_progress > 0 ? `${s.in_progress} live` : null,
    s.no_show > 0 ? `⚠ ${s.no_show} no-show` : null,
    s.cancelled > 0 ? `${s.cancelled} cancelled` : null,
    s.sub_in > 0 ? `${s.sub_in} covered for others` : null,
    s.off_plan > 0 ? `+${s.off_plan} off-plan` : null,
  ].filter(Boolean);

  return (
    <div className="flex flex-col gap-2 border-b py-3 last:border-b-0">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className={`text-base ${priorityTone(s)}`} aria-hidden>
          {priorityIcon(s)}
        </span>
        <span className="font-medium">
          {teacher.first_name} {teacher.last_name}
        </span>
        <span className="text-xs text-muted-foreground">
          {summaryParts.join(" · ") || "no activity today"}
        </span>
      </div>
      {teacher.events.length > 0 && (
        <div className="flex flex-wrap gap-2 pl-6">
          {teacher.events.map((ev) => (
            <EventPill key={ev.id} event={ev} onClick={onEventClick} />
          ))}
        </div>
      )}
    </div>
  );
}
