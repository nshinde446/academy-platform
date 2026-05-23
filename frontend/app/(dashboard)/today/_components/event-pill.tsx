"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { RosterEvent } from "../_schemas/roster";

interface EventPillProps {
  event: RosterEvent;
  onClick?: (event: RosterEvent) => void;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function EventPill({ event, onClick }: EventPillProps) {
  const start = formatTime(event.start);
  const end = event.end ? formatTime(event.end) : "";
  const window = end ? `${start}–${end}` : start;

  // Subject / batch line. Sessions can span multiple batches.
  const batches =
    event.kind === "session" && event.batch_names.length > 0
      ? event.batch_names.join(", ")
      : event.batch_name ?? "—";
  const context = [event.subject_name, batches].filter(Boolean).join(" · ");

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={() => onClick?.(event)}
      className="h-auto flex-col items-start gap-1 px-3 py-2 text-left"
      aria-label={`${event.status_label} ${context} ${window}`}
    >
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-muted-foreground tabular-nums">
          {window}
        </span>
        <Badge variant={event.status_tone}>{event.status_label}</Badge>
        {event.status_sub && (
          <span className="text-[10px] text-muted-foreground">
            {event.status_sub}
          </span>
        )}
      </div>
      <div className="text-xs">
        <span className="font-medium">{event.subject_name ?? "—"}</span>
        <span className="text-muted-foreground"> · {batches}</span>
        {event.topic_name && (
          <span className="text-muted-foreground"> · {event.topic_name}</span>
        )}
      </div>
      {event.kind === "lecture" && event.actual_teacher_name && (
        <span className="text-[10px] text-muted-foreground">
          covered by {event.actual_teacher_name}
        </span>
      )}
    </Button>
  );
}
