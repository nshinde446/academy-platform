"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
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

// Above this many sessions the table gets long and low-signal, so we switch to
// a horizontally-scrollable strip of cards ("sliders if the list is huge").
const SLIDER_THRESHOLD = 6;

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

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "2-digit",
    year: "numeric",
  });
}

function formatTimeRange(startIso: string, endIso: string | null): string {
  const s = new Date(startIso);
  if (Number.isNaN(s.getTime())) return "";
  const opts: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit" };
  const start = s.toLocaleTimeString(undefined, opts);
  if (!endIso) return start;
  const e = new Date(endIso);
  if (Number.isNaN(e.getTime())) return start;
  const mins = Math.round((e.getTime() - s.getTime()) / 60000);
  const dur = mins >= 60 ? `${Math.floor(mins / 60)}h ${mins % 60}m` : `${mins}m`;
  return `${start} – ${e.toLocaleTimeString(undefined, opts)} · ${dur}`;
}

export function SessionList({
  sessions,
  batches,
  teachers,
  subjects,
}: SessionListProps) {
  if (sessions.length === 0) return null;

  const useSlider = sessions.length > SLIDER_THRESHOLD;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold">Recorded sessions</h3>
          <p className="text-sm text-muted-foreground">
            Actual teaching events — makeup classes and ad-hoc sessions that
            happened outside the schedule.
          </p>
        </div>
        <span className="text-xs tabular-nums text-muted-foreground">
          {sessions.length} session{sessions.length === 1 ? "" : "s"}
        </span>
      </div>

      {useSlider ? (
        <SessionSlider
          sessions={sessions}
          batches={batches}
          teachers={teachers}
          subjects={subjects}
        />
      ) : (
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
      )}
    </div>
  );
}

function SessionSlider({
  sessions,
  batches,
  teachers,
  subjects,
}: SessionListProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);

  const syncEdges = useCallback(() => {
    const el = trackRef.current;
    if (!el) return;
    // 1px slack absorbs sub-pixel rounding at the extremes.
    setAtStart(el.scrollLeft <= 1);
    setAtEnd(el.scrollLeft + el.clientWidth >= el.scrollWidth - 1);
  }, []);

  useEffect(() => {
    syncEdges();
  }, [syncEdges, sessions.length]);

  const scrollByCards = useCallback((dir: 1 | -1) => {
    const el = trackRef.current;
    if (!el) return;
    // Page by ~80% of the visible width so a couple of cards stay for context.
    el.scrollBy({ left: dir * el.clientWidth * 0.8, behavior: "smooth" });
  }, []);

  return (
    <div className="relative">
      <div
        ref={trackRef}
        onScroll={syncEdges}
        className="flex snap-x snap-mandatory gap-3 overflow-x-auto scroll-smooth pb-2 [scrollbar-width:thin]"
        role="group"
        aria-label="Recorded sessions"
      >
        {sessions.map((s) => {
          const t = teachers.find((x) => x.id === s.teacher_id);
          const subj = subjects.find((x) => x.id === s.subject_id);
          const batchNames = s.batch_ids
            .map((bid) => batches.find((b) => b.id === bid)?.name ?? "?")
            .join(", ");
          return (
            <article
              key={s.id}
              className="flex w-64 shrink-0 snap-start flex-col gap-2 rounded-xl border bg-card p-4 shadow-sm ring-1 ring-foreground/10"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium tabular-nums">
                    {formatDate(s.actual_start)}
                  </div>
                  <div className="text-xs text-muted-foreground tabular-nums">
                    {formatTimeRange(s.actual_start, s.actual_end)}
                  </div>
                </div>
                <Badge variant={ORIGIN_VARIANTS[s.origin] ?? "default"}>
                  {s.origin}
                </Badge>
              </div>
              <div className="truncate text-sm font-medium">
                {t ? `${t.first_name} ${t.last_name}` : "—"}
              </div>
              <div className="truncate text-xs text-muted-foreground">
                {subj?.name ?? "—"}
                {batchNames ? ` · ${batchNames}` : ""}
              </div>
              {s.notes && (
                <p className="line-clamp-2 text-xs text-muted-foreground">
                  {s.notes}
                </p>
              )}
            </article>
          );
        })}
      </div>

      {/* Edge fades hint that more cards lie beyond the viewport. */}
      <div
        aria-hidden
        className={cn(
          "pointer-events-none absolute inset-y-0 left-0 w-10 bg-gradient-to-r from-background to-transparent transition-opacity",
          atStart && "opacity-0",
        )}
      />
      <div
        aria-hidden
        className={cn(
          "pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-background to-transparent transition-opacity",
          atEnd && "opacity-0",
        )}
      />

      <SliderArrow
        side="left"
        onClick={() => scrollByCards(-1)}
        disabled={atStart}
      />
      <SliderArrow side="right" onClick={() => scrollByCards(1)} disabled={atEnd} />
    </div>
  );
}

function SliderArrow({
  side,
  onClick,
  disabled,
}: {
  side: "left" | "right";
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={side === "left" ? "Previous sessions" : "Next sessions"}
      className={cn(
        "absolute top-1/2 z-10 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-full border bg-card text-muted-foreground shadow-sm ring-1 ring-foreground/10 transition-colors hover:text-foreground disabled:pointer-events-none disabled:opacity-0",
        side === "left" ? "left-1" : "right-1",
      )}
    >
      {side === "left" ? "‹" : "›"}
    </button>
  );
}
