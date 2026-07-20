"use client";

import { useMemo, useState } from "react";
import { useUserStore } from "@/store/user-store";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  useBatchesForLectures,
  useLectures,
} from "../lectures/_hooks/use-lectures";
import { useStudentsWithStats } from "../students/_hooks/use-students";
import type { LectureResponse } from "../lectures/_schemas/lecture";
import {
  useLectureAttendance,
  useMarkAttendance,
} from "./_hooks/use-attendance";
import type {
  AttendanceRecord,
  AttendanceStatus,
} from "./_schemas/attendance";
import { PageHeader } from "@/components/layout/page-header";
import { AttendanceRoster } from "./_components/attendance-roster";
import { DayRegister } from "./_components/day-register";

const SELECT_CLASS =
  "h-9 rounded-lg border border-input bg-background px-3 text-sm";

type AttendanceView = "lecture" | "day";

function formatLectureLabel(
  l: LectureResponse,
  batchName: string,
): string {
  const d = new Date(l.scheduled_start);
  const when = Number.isNaN(d.getTime())
    ? l.scheduled_start
    : d.toLocaleString(undefined, {
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
  return `${when} · ${batchName || "Batch"} · ${l.lecture_status}`;
}

function isToday(iso: string): boolean {
  const d = new Date(iso);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

export default function AttendancePage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const lecturesQuery = useLectures(branchId);
  const batchesQuery = useBatchesForLectures(branchId);
  const studentsQuery = useStudentsWithStats(branchId);

  const lectures = useMemo(() => lecturesQuery.data ?? [], [lecturesQuery.data]);
  const batches = useMemo(() => batchesQuery.data ?? [], [batchesQuery.data]);
  const students = useMemo(() => studentsQuery.data ?? [], [studentsQuery.data]);

  const [view, setView] = useState<AttendanceView>("lecture");
  const [filterBatchId, setFilterBatchId] = useState("");
  const [selectedLectureId, setSelectedLectureId] = useState("");
  const [pendingStudentId, setPendingStudentId] = useState<string | null>(null);
  const [isBulk, setIsBulk] = useState(false);
  const toast = useToast();

  const lookupBatchName = (id: string) =>
    batches.find((b) => b.id === id)?.name ?? "";

  // Lectures the picker shows: optionally narrowed by batch, newest first.
  const pickerLectures = useMemo(() => {
    const list = filterBatchId
      ? lectures.filter((l) => l.batch_id === filterBatchId)
      : lectures;
    return [...list].sort(
      (a, b) =>
        new Date(b.scheduled_start).getTime() -
        new Date(a.scheduled_start).getTime(),
    );
  }, [lectures, filterBatchId]);

  // Derived default — today's lecture first, else newest. Falling back this
  // way (instead of writing to state in an effect) keeps the selection valid
  // when the batch filter changes the available list.
  const effectiveLectureId = useMemo(() => {
    if (selectedLectureId) return selectedLectureId;
    if (pickerLectures.length === 0) return "";
    const todays = pickerLectures.find((l) => isToday(l.scheduled_start));
    return (todays ?? pickerLectures[0]).id;
  }, [selectedLectureId, pickerLectures]);

  const selectedLecture = useMemo(
    () => lectures.find((l) => l.id === effectiveLectureId) ?? null,
    [lectures, effectiveLectureId],
  );

  const attendanceQuery = useLectureAttendance(branchId, effectiveLectureId || undefined);
  const markMutation = useMarkAttendance(branchId, effectiveLectureId || undefined);

  const recordByStudent = useMemo(() => {
    const map = new Map<string, AttendanceRecord>();
    for (const r of attendanceQuery.data ?? []) map.set(r.student_id, r);
    return map;
  }, [attendanceQuery.data]);

  // Roster = students in the selected lecture's batch, alphabetical.
  const roster = useMemo(() => {
    if (!selectedLecture) return [];
    return students
      .filter((s) => s.batch_id === selectedLecture.batch_id)
      .map((s) => ({
        id: s.id,
        first_name: s.first_name,
        last_name: s.last_name,
        enrollment_number: s.enrollment_number,
      }))
      .sort((a, b) =>
        `${a.first_name} ${a.last_name}`.localeCompare(
          `${b.first_name} ${b.last_name}`,
        ),
      );
  }, [students, selectedLecture]);

  const kpis = useMemo(() => {
    let present = 0;
    let absent = 0;
    let late = 0;
    let excused = 0;
    let marked = 0;
    for (const s of roster) {
      const rec = recordByStudent.get(s.id);
      if (!rec) continue;
      marked += 1;
      if (rec.attendance_status === "PRESENT") present += 1;
      else if (rec.attendance_status === "ABSENT") absent += 1;
      else if (rec.attendance_status === "LATE") late += 1;
      else if (rec.attendance_status === "EXCUSED") excused += 1;
    }
    const total = roster.length;
    const pct = total > 0 ? ((present + late) / total) * 100 : 0;
    return { present, absent, late, excused, marked, total, pct };
  }, [roster, recordByStudent]);

  function errorOf(err: unknown): string {
    const e = err as {
      response?: { data?: { error?: { message?: string }; detail?: string } };
    };
    return (
      e?.response?.data?.error?.message ||
      e?.response?.data?.detail ||
      "Action failed"
    );
  }

  async function handleMark(studentId: string, status: AttendanceStatus) {
    setPendingStudentId(studentId);
    try {
      await markMutation.mutateAsync({
        student_id: studentId,
        attendance_status: status,
      });
    } catch (err) {
      toast.error(errorOf(err));
    } finally {
      setPendingStudentId(null);
    }
  }

  async function handleMarkAllPresent() {
    if (roster.length === 0) return;
    setIsBulk(true);
    try {
      // Only fill in students not already marked, to avoid needless writes.
      const targets = roster.filter((s) => !recordByStudent.has(s.id));
      await Promise.all(
        targets.map((s) =>
          markMutation.mutateAsync({
            student_id: s.id,
            attendance_status: "PRESENT",
          }),
        ),
      );
    } catch (err) {
      toast.error(errorOf(err));
    } finally {
      setIsBulk(false);
    }
  }

  const busy = isBulk || markMutation.isPending;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Attendance"
        description="Mark a lecture roster by hand. Biometric punches from the BioMax device arrive automatically — no manual pull needed. Marks upsert per student, and changing one overwrites the previous status."
        actions={
          view === "lecture" ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!selectedLecture || roster.length === 0 || busy}
              onClick={handleMarkAllPresent}
            >
              Mark all present
            </Button>
          ) : undefined
        }
      >
        {/* View toggle — per-lecture roster vs whole-day campus register */}
        <div
          role="tablist"
          aria-label="Attendance view"
          className="inline-flex w-fit overflow-hidden rounded-lg border"
        >
          {(["lecture", "day"] as const).map((v) => (
            <button
              key={v}
              type="button"
              role="tab"
              aria-selected={view === v}
              onClick={() => setView(v)}
              className={
                "h-8 px-4 text-sm font-medium transition-colors " +
                (view === v
                  ? "bg-primary text-primary-foreground"
                  : "bg-background text-muted-foreground hover:bg-muted hover:text-foreground")
              }
            >
              {v === "lecture" ? "By lecture" : "By day"}
            </button>
          ))}
        </div>
      </PageHeader>

      {view === "day" ? (
        <DayRegister branchId={branchId} batches={batches} />
      ) : (
      <>
      {/* Lecture picker */}
      <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-center">
        <select
          value={filterBatchId}
          onChange={(e) => {
            setFilterBatchId(e.target.value);
            setSelectedLectureId("");
          }}
          className={SELECT_CLASS}
          aria-label="Filter by batch"
        >
          <option value="">All batches</option>
          {batches.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <select
          value={effectiveLectureId}
          onChange={(e) => setSelectedLectureId(e.target.value)}
          className={`${SELECT_CLASS} min-w-0 flex-1 lg:max-w-md`}
          aria-label="Select lecture"
        >
          <option value="">Select a lecture…</option>
          {pickerLectures.map((l) => (
            <option key={l.id} value={l.id}>
              {formatLectureLabel(l, lookupBatchName(l.batch_id))}
            </option>
          ))}
        </select>
      </div>

      {/* KPI strip */}
      {selectedLecture && (
        <Card size="sm">
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <Kpi label="Attendance" value={`${kpis.pct.toFixed(0)}%`} tone={kpis.pct < 60 ? "destructive" : "success"} />
              <Kpi label="Present" value={String(kpis.present)} />
              <Kpi label="Late" value={String(kpis.late)} />
              <Kpi label="Absent" value={String(kpis.absent)} />
              <Kpi label="Excused" value={String(kpis.excused)} />
              <Kpi label="Marked" value={`${kpis.marked}/${kpis.total}`} />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Content */}
      {!branchId ? (
        <p className="text-muted-foreground text-sm">No branch selected.</p>
      ) : lecturesQuery.isLoading ? (
        <TableSkeleton rows={6} />
      ) : lecturesQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to load lectures. Make sure the backend is running.
        </p>
      ) : !selectedLecture ? (
        <p className="text-muted-foreground text-sm">
          Select a lecture above to take attendance.
        </p>
      ) : roster.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No students are enrolled in this lecture&apos;s batch yet.
        </p>
      ) : (
        <AttendanceRoster
          roster={roster}
          recordByStudent={recordByStudent}
          onMark={handleMark}
          pendingStudentId={pendingStudentId}
          disabled={isBulk}
        />
      )}

      </>
      )}
    </div>
  );
}

function Kpi({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "success" | "destructive";
}) {
  const cls =
    tone === "destructive"
      ? "text-destructive"
      : tone === "success"
        ? "text-emerald-600 dark:text-emerald-400"
        : "text-foreground";
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`text-xl font-semibold tabular-nums ${cls}`}>
        {value}
      </span>
    </div>
  );
}
