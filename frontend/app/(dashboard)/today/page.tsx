"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useUserStore } from "@/store/user-store";
import { useRoster } from "./_hooks/use-roster";
import { SnapshotStrip } from "./_components/snapshot-strip";
import { LiveNowStrip } from "./_components/live-now-strip";
import { TeacherRow } from "./_components/teacher-row";
import { IdleTeachers } from "./_components/idle-teachers";
import {
  useCompleteLecture,
  useLectures,
  useMarkNoShow,
  useMarkSubstitute,
  useStartLecture,
  useTeachers,
} from "../lectures/_hooks/use-lectures";
import { MarkSubstituteDialog } from "../lectures/_components/mark-substitute-dialog";
import { MarkNoShowDialog } from "../lectures/_components/mark-no-show-dialog";
import type {
  LectureNoShow,
  LectureResponse,
  LectureSubstitute,
} from "../lectures/_schemas/lecture";
import type { RosterEvent } from "./_schemas/roster";

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function shiftIsoDate(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export default function TodayPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [date, setDate] = useState(isoToday());

  const rosterQuery = useRoster(branchId, date);
  const lecturesQuery = useLectures(branchId);
  const teachersQuery = useTeachers(branchId);

  // The roster is presentation-only; mutating still goes through the
  // existing lecture-page mutations. Pulling the same hooks means the
  // dialog state lives here without a refactor.
  const startMutation = useStartLecture(branchId);
  const completeMutation = useCompleteLecture(branchId);
  const substituteMutation = useMarkSubstitute(branchId);
  const noShowMutation = useMarkNoShow(branchId);

  const allLectures = lecturesQuery.data ?? [];
  const teachers = teachersQuery.data ?? [];

  const [substituteTarget, setSubstituteTarget] =
    useState<LectureResponse | null>(null);
  const [substituteOpen, setSubstituteOpen] = useState(false);
  const [noShowTarget, setNoShowTarget] = useState<LectureResponse | null>(null);
  const [noShowOpen, setNoShowOpen] = useState(false);
  const [alertMessage, setAlertMessage] = useState<string | null>(null);

  function findLecture(id: string): LectureResponse | null {
    return allLectures.find((l) => l.id === id) ?? null;
  }

  async function withErrorAlert<T>(p: Promise<T>) {
    try {
      await p;
    } catch (err: any) {
      const msg =
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        "Action failed";
      setAlertMessage(msg);
    }
  }

  function handleEventClick(ev: RosterEvent) {
    if (ev.kind === "session") {
      // Sessions are read-only from the roster. Keep it simple: show notes.
      return;
    }
    const lecture = findLecture(ev.id);
    if (!lecture) return;

    // Route the click based on current lecture status.
    const status = lecture.lecture_status;
    if (status === "scheduled" || status === "rescheduled") {
      // Past start time → offer No-Show or Start; future → just Start.
      const isOverdue = new Date(lecture.scheduled_start) < new Date();
      if (isOverdue) {
        setNoShowTarget(lecture);
        setNoShowOpen(true);
      } else {
        withErrorAlert(startMutation.mutateAsync(lecture.id));
      }
      return;
    }
    if (status === "started" || status === "paused") {
      withErrorAlert(completeMutation.mutateAsync(lecture.id));
      return;
    }
    if (status === "completed" || status === "no_show") {
      // After-the-fact correction. Substitute also handles no_show → completed.
      setSubstituteTarget(lecture);
      setSubstituteOpen(true);
      return;
    }
    if (status === "cancelled") {
      // No primary action; offer record-makeup via the Lectures page.
      setAlertMessage(
        "Cancelled lectures can be made up via Record Makeup on the Lectures page.",
      );
      return;
    }
  }

  async function handleSubstituteSubmit(data: LectureSubstitute) {
    if (!substituteTarget) return;
    await substituteMutation.mutateAsync({
      lectureId: substituteTarget.id,
      data,
    });
  }

  async function handleNoShowSubmit(data: LectureNoShow) {
    if (!noShowTarget) return;
    await noShowMutation.mutateAsync({ lectureId: noShowTarget.id, data });
  }

  const today = isoToday();
  const friendly = (() => {
    if (date === today) return "Today";
    if (date === shiftIsoDate(today, 1)) return "Tomorrow";
    if (date === shiftIsoDate(today, -1)) return "Yesterday";
    return new Date(`${date}T00:00:00Z`).toLocaleDateString(undefined, {
      weekday: "long",
      year: "numeric",
      month: "short",
      day: "2-digit",
    });
  })();

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">{friendly}</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Live roster of every teacher&apos;s day. Click a class to start,
            complete, mark no-show, or record a substitute.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setDate(shiftIsoDate(date, -1))}
            aria-label="Previous day"
          >
            ◀
          </Button>
          <Input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-44"
            aria-label="Pick date"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => setDate(shiftIsoDate(date, 1))}
            aria-label="Next day"
          >
            ▶
          </Button>
          <Button variant="outline" size="sm" onClick={() => setDate(today)}>
            Today
          </Button>
        </div>
      </div>

      {rosterQuery.isLoading && (
        <p className="text-muted-foreground text-sm">Loading roster…</p>
      )}
      {rosterQuery.isError && (
        <p className="text-destructive text-sm">
          Failed to load roster. Make sure the backend is running.
        </p>
      )}

      {rosterQuery.data && (
        <>
          <SnapshotStrip snapshot={rosterQuery.data.snapshot} />
          <LiveNowStrip
            liveNow={rosterQuery.data.live_now}
            now={rosterQuery.data.now}
          />

          {rosterQuery.data.teachers.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              No lectures or sessions for this date. Pick another day or use{" "}
              <a href="/lectures" className="underline">
                Schedule Lecture
              </a>
              .
            </p>
          ) : (
            <div className="rounded-xl border ring-1 ring-foreground/10 px-4">
              {rosterQuery.data.teachers.map((t) => (
                <TeacherRow
                  key={t.teacher_id}
                  teacher={t}
                  onEventClick={handleEventClick}
                />
              ))}
              <IdleTeachers teachers={rosterQuery.data.idle_teachers} />
            </div>
          )}
        </>
      )}

      <MarkSubstituteDialog
        lecture={substituteTarget}
        teachers={teachers}
        open={substituteOpen}
        onOpenChange={(o) => {
          setSubstituteOpen(o);
          if (!o) setSubstituteTarget(null);
        }}
        onSubmit={handleSubstituteSubmit}
        isPending={substituteMutation.isPending}
      />

      <MarkNoShowDialog
        lecture={noShowTarget}
        open={noShowOpen}
        onOpenChange={(o) => {
          setNoShowOpen(o);
          if (!o) setNoShowTarget(null);
        }}
        onSubmit={handleNoShowSubmit}
        isPending={noShowMutation.isPending}
      />

      <ConfirmDialog
        open={!!alertMessage}
        onOpenChange={(o) => !o && setAlertMessage(null)}
        title="Action info"
        description={alertMessage ?? ""}
        confirmLabel="OK"
        hideCancel
      />
    </div>
  );
}
