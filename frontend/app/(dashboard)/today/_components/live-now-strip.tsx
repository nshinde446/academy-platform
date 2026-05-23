"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { RosterLiveNow } from "../_schemas/roster";

interface LiveNowStripProps {
  liveNow: RosterLiveNow[];
  now: string;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function LiveNowStrip({ liveNow, now }: LiveNowStripProps) {
  if (liveNow.length === 0) return null;

  const nowLabel = new Date(now).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Right now · {nowLabel}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-2">
          {liveNow.map((ev) => {
            const window = `${formatTime(ev.scheduled_start)}–${formatTime(ev.scheduled_end)}`;
            const context = [ev.subject_name, ev.batch_name, ev.classroom_name]
              .filter(Boolean)
              .join(" · ");
            return (
              <div
                key={ev.lecture_id}
                className="flex flex-wrap items-center gap-2 text-sm"
              >
                <Badge
                  variant={ev.kind === "live" ? "success" : "destructive"}
                >
                  {ev.kind === "live" ? "Live" : "Overdue"}
                </Badge>
                <span className="font-medium">{ev.teacher_name}</span>
                <span className="text-muted-foreground">{context}</span>
                <span className="text-muted-foreground">· {window}</span>
                {ev.topic_name && (
                  <span className="text-muted-foreground">
                    · {ev.topic_name}
                  </span>
                )}
                {ev.kind === "overdue" && (
                  <span className="text-destructive text-xs">
                    {ev.minutes_overdue} min overdue · not started
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
