"use client";

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQueries } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import { useUserStore } from "@/store/user-store";
import { useDebounce } from "@/hooks/use-debounce";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {
  subjectKeys,
  topicKeys,
  useBatchesForLectures,
  useCancelLecture,
  useCompleteLecture,
  useCopySelected,
  useCreateLecture,
  useCreateLectureSession,
  useDeleteLecture,
  useDppCoverage,
  useLectures,
  useLectureSessions,
  useLecturesInRange,
  useMarkNoShow,
  useMarkSubstitute,
  usePendingActuals,
  usePendingMakeups,
  useStartLecture,
  useUpdateActuals,
  useClassrooms,
  useTeachers,
} from "./_hooks/use-lectures";
import type {
  LectureActuals,
  LectureCreate,
  LectureNoShow,
  LectureResponse,
  LectureSessionCreate,
  LectureStatus,
  LectureSubstitute,
  SubjectSummary,
  TopicSummary,
} from "./_schemas/lecture";
import { LectureTable } from "./_components/lecture-table";
import {
  LectureTableMsa,
  groupStatus,
  type MsaStatusGroup,
} from "./_components/lecture-table-msa";
import { GenerateDppModal } from "./_components/generate-dpp-modal";
import { LectureEmptyState } from "./_components/lecture-empty-state";
import { CreateLectureDialog } from "./_components/create-lecture-dialog";
import { MarkSubstituteDialog } from "./_components/mark-substitute-dialog";
import { MarkNoShowDialog } from "./_components/mark-no-show-dialog";
import { RecordMakeupDialog } from "./_components/record-makeup-dialog";
import { ImportScheduleDialog } from "./_components/import-schedule-dialog";
import { CopyScheduleDialog } from "./_components/copy-schedule-dialog";
import { EndOfDayDialog } from "./_components/end-of-day-dialog";
import { TeacherProductivityPanel } from "./_components/teacher-productivity-panel";
import { SessionList } from "./_components/session-list";
import { downloadScheduleCsv } from "./_lib/export-schedule";
import { TimetableDialog } from "./_components/timetable-dialog";
import { HolidaysDialog } from "./_components/holidays-dialog";
import { PendingActualsPanel } from "./_components/pending-actuals-panel";
import { MakeupQueuePanel } from "./_components/makeup-queue-panel";
import { CalendarWeekView } from "./_components/calendar-week-view";
import { TeacherLeaveDialog } from "./_components/teacher-leave-dialog";

const SELECT_CLASS =
  "h-9 rounded-lg border border-input bg-background px-3 text-sm";

const STATUS_OPTIONS: LectureStatus[] = [
  "scheduled",
  "started",
  "paused",
  "completed",
  "cancelled",
  "rescheduled",
];

function inRange(
  iso: string,
  fromIsoDate: string,
  toIsoDate: string
): boolean {
  if (!fromIsoDate && !toIsoDate) return true;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return true;
  if (fromIsoDate) {
    const from = new Date(`${fromIsoDate}T00:00:00`);
    if (d < from) return false;
  }
  if (toIsoDate) {
    const to = new Date(`${toIsoDate}T23:59:59`);
    if (d > to) return false;
  }
  return true;
}

function filterLectures(
  lectures: LectureResponse[],
  search: string,
  batchId: string,
  teacherId: string,
  status: string,
  fromDate: string,
  toDate: string,
  lookupBatch: (id: string) => string,
  lookupTeacher: (id: string) => string
): LectureResponse[] {
  const q = search.toLowerCase();
  return lectures.filter((l) => {
    if (batchId && l.batch_id !== batchId) return false;
    if (teacherId && l.teacher_id !== teacherId) return false;
    if (status && l.lecture_status !== status) return false;
    if (!inRange(l.scheduled_start, fromDate, toDate)) return false;
    if (!q) return true;
    const hay = `${lookupBatch(l.batch_id)} ${lookupTeacher(
      l.teacher_id
    )}`.toLowerCase();
    return hay.includes(q);
  });
}

const MSA_GROUPS: { value: MsaStatusGroup | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "scheduled", label: "Scheduled" },
  { value: "live", label: "Live" },
  { value: "completed", label: "Completed" },
  { value: "no_show", label: "No-show" },
];

function startOfWeekMonday(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  const day = x.getDay(); // 0 Sun … 6 Sat
  x.setDate(x.getDate() + (day === 0 ? -6 : 1 - day)); // back to Monday
  return x;
}

function addDaysDate(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

function tomorrowIso(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  const shifted = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 10);
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

function isThisWeek(iso: string): boolean {
  const d = new Date(iso);
  const now = new Date();
  const day = now.getDay(); // 0 Sun … 6 Sat
  const start = new Date(now);
  start.setDate(now.getDate() - day);
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(start.getDate() + 7);
  return d >= start && d < end;
}

export default function LecturesPage() {
  // useSearchParams forces the page to opt out of static prerendering, so
  // we wrap the body in <Suspense> per the Next 16 build requirement.
  return (
    <Suspense fallback={<p className="text-muted-foreground text-sm">Loading lectures...</p>}>
      <LecturesPageBody />
    </Suspense>
  );
}

function LecturesPageBody() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const searchParams = useSearchParams();
  const view = searchParams.get("view");
  const isMsa = view === "msa";
  const isCalendar = view === "calendar";

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);
  const [filterBatchId, setFilterBatchId] = useState("");
  const [filterTeacherId, setFilterTeacherId] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [msaGroup, setMsaGroup] = useState<MsaStatusGroup | "all">("all");

  const [deleteTarget, setDeleteTarget] = useState<LectureResponse | null>(
    null
  );
  const [substituteTarget, setSubstituteTarget] =
    useState<LectureResponse | null>(null);
  const [substituteOpen, setSubstituteOpen] = useState(false);
  const [noShowTarget, setNoShowTarget] = useState<LectureResponse | null>(
    null
  );
  const [noShowOpen, setNoShowOpen] = useState(false);
  const [dppTarget, setDppTarget] = useState<LectureResponse | null>(null);
  const [dppOpen, setDppOpen] = useState(false);
  const [makeupOpen, setMakeupOpen] = useState(false);
  const [makeupPrefillId, setMakeupPrefillId] = useState<string | null>(null);
  const [actualsTarget, setActualsTarget] = useState<LectureResponse | null>(
    null
  );
  const [actualsOpen, setActualsOpen] = useState(false);
  const toast = useToast();

  // Which "Manage" tool dialog is open (driven from the header overflow menu).
  const [tool, setTool] = useState<
    "timetable" | "holidays" | "leave" | "copy" | null
  >(null);

  // Row selection for "copy selected to date" — explicit, no by-date guess.
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [copyTargetDate, setCopyTargetDate] = useState("");
  const [deleteSelectedOpen, setDeleteSelectedOpen] = useState(false);

  // Calendar week view — the Monday of the week currently shown.
  const [weekStart, setWeekStart] = useState<Date>(() =>
    startOfWeekMonday(new Date()),
  );
  const calFrom = weekStart.toISOString();
  const calTo = addDaysDate(weekStart, 7).toISOString();
  const calendarQuery = useLecturesInRange(
    branchId,
    isCalendar ? calFrom : "",
    isCalendar ? calTo : "",
  );

  const lecturesQuery = useLectures(branchId);
  const pendingActualsQuery = usePendingActuals(branchId);
  const pendingMakeupsQuery = usePendingMakeups(branchId);
  const sessionsQuery = useLectureSessions(branchId);
  const dppCoverageQuery = useDppCoverage(branchId);
  const batchesQuery = useBatchesForLectures(branchId);
  const teachersQuery = useTeachers(branchId);
  const classroomsQuery = useClassrooms(branchId);

  const createMutation = useCreateLecture(branchId);
  const startMutation = useStartLecture(branchId);
  const completeMutation = useCompleteLecture(branchId);
  const cancelMutation = useCancelLecture(branchId);
  const deleteMutation = useDeleteLecture(branchId);
  const substituteMutation = useMarkSubstitute(branchId);
  const noShowMutation = useMarkNoShow(branchId);
  const sessionMutation = useCreateLectureSession(branchId);
  const actualsMutation = useUpdateActuals(branchId);
  const copySelectedMutation = useCopySelected(branchId);

  const batches = batchesQuery.data ?? [];
  const teachers = teachersQuery.data ?? [];
  const classrooms = classroomsQuery.data ?? [];
  const lectures = lecturesQuery.data ?? [];
  const pendingActuals = pendingActualsQuery.data ?? [];
  const pendingMakeups = pendingMakeupsQuery.data ?? [];
  const sessions = sessionsQuery.data ?? [];

  // Resolve all subjects/topics referenced by the visible lectures so the
  // table can render their names. Group lectures by the (batch.course_id,
  // subject_id) they reference, then load. To keep this dashboard simple,
  // we fetch subjects per unique course on-page and topics per unique subject.
  const calendarLectures = calendarQuery.data ?? [];
  const uniqueCourseIds = useMemo(() => {
    const set = new Set<string>();
    for (const l of [...lectures, ...calendarLectures]) {
      const b = batches.find((x) => x.id === l.batch_id);
      if (b) set.add(b.course_id);
    }
    for (const s of sessions) {
      for (const bid of s.batch_ids) {
        const b = batches.find((x) => x.id === bid);
        if (b) set.add(b.course_id);
      }
    }
    return Array.from(set);
  }, [lectures, calendarLectures, sessions, batches]);

  const uniqueSubjectIds = useMemo(() => {
    const set = new Set<string>();
    for (const l of lectures) set.add(l.subject_id);
    for (const l of calendarLectures) set.add(l.subject_id);
    for (const s of sessions) set.add(s.subject_id);
    return Array.from(set);
  }, [lectures, calendarLectures, sessions]);

  // useQueries lets the count vary with the data without breaking the
  // Rules of Hooks. React Query dedupes by queryKey across the page.
  const subjectQueries = useQueries({
    queries: uniqueCourseIds.map((cid) => ({
      queryKey: subjectKeys.byCourse(branchId ?? "", cid),
      queryFn: async () => {
        const res = await apiClient.get<SubjectSummary[]>(
          "/api/v1/academic/subjects",
          { params: { branch_id: branchId, course_id: cid } }
        );
        return res.data;
      },
      enabled: !!branchId && !!cid,
    })),
  });

  const topicQueries = useQueries({
    queries: uniqueSubjectIds.map((sid) => ({
      queryKey: topicKeys.bySubject(branchId ?? "", sid),
      queryFn: async () => {
        const res = await apiClient.get<TopicSummary[]>(
          "/api/v1/academic/topics",
          { params: { branch_id: branchId, subject_id: sid } }
        );
        return res.data;
      },
      enabled: !!branchId && !!sid,
    })),
  });

  const coveredLectureIds = useMemo(() => {
    const set = new Set<string>();
    for (const s of sessions) {
      for (const lid of s.lecture_ids) set.add(lid);
    }
    return set;
  }, [sessions]);

  const allSubjects: SubjectSummary[] = useMemo(() => {
    const map = new Map<string, SubjectSummary>();
    for (const q of subjectQueries) {
      for (const s of (q.data as SubjectSummary[] | undefined) ?? [])
        map.set(s.id, s);
    }
    return Array.from(map.values());
  }, [subjectQueries]);

  const allTopics: TopicSummary[] = useMemo(() => {
    const map = new Map<string, TopicSummary>();
    for (const q of topicQueries) {
      for (const t of (q.data as TopicSummary[] | undefined) ?? [])
        map.set(t.id, t);
    }
    return Array.from(map.values());
  }, [topicQueries]);

  const lookupBatchName = (id: string) =>
    batches.find((b) => b.id === id)?.name ?? "";
  const lookupTeacherName = (id: string) => {
    const t = teachers.find((x) => x.id === id);
    return t ? `${t.first_name} ${t.last_name}` : "";
  };

  const filtered = useMemo(
    () =>
      filterLectures(
        lectures,
        debouncedSearch,
        filterBatchId,
        filterTeacherId,
        filterStatus,
        fromDate,
        toDate,
        lookupBatchName,
        lookupTeacherName
      ),
    [
      lectures,
      debouncedSearch,
      filterBatchId,
      filterTeacherId,
      filterStatus,
      fromDate,
      toDate,
      batches,
      teachers,
    ]
  );

  // MSA view: drop cancelled rows entirely, group statuses, then apply chip.
  const msaFiltered = useMemo(() => {
    const q = debouncedSearch.toLowerCase();
    return lectures.filter((l) => {
      const g = groupStatus(l.lecture_status);
      if (!g) return false;
      if (msaGroup !== "all" && g !== msaGroup) return false;
      if (!q) return true;
      const t = teachers.find((x) => x.id === l.teacher_id);
      const at = teachers.find((x) => x.id === l.actual_teacher_id);
      const b = batches.find((x) => x.id === l.batch_id);
      const top = allTopics.find((x) => x.id === l.topic_id);
      const hay = [
        t ? `${t.first_name} ${t.last_name}` : "",
        at ? `${at.first_name} ${at.last_name}` : "",
        b?.name ?? "",
        top?.name ?? "",
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [lectures, msaGroup, debouncedSearch, teachers, batches, allTopics]);

  const msaKpis = useMemo(() => {
    const eligible = lectures.filter((l) => !!groupStatus(l.lecture_status));
    const thisWeek = eligible.filter((l) => isThisWeek(l.scheduled_start)).length;
    const completed = eligible.filter(
      (l) => groupStatus(l.lecture_status) === "completed" && isThisWeek(l.scheduled_start)
    ).length;
    const live = eligible.filter(
      (l) => groupStatus(l.lecture_status) === "live"
    ).length;
    const upcomingToday = eligible.filter(
      (l) =>
        groupStatus(l.lecture_status) === "scheduled" &&
        isToday(l.scheduled_start)
    ).length;
    return { thisWeek, completed, live, upcomingToday };
  }, [lectures]);

  async function handleCreate(data: LectureCreate) {
    await createMutation.mutateAsync(data);
  }

  async function handleRecordSession(data: LectureSessionCreate) {
    await sessionMutation.mutateAsync(data);
  }

  async function withErrorAlert<T>(p: Promise<T>) {
    try {
      await p;
    } catch (err: any) {
      const msg =
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        "Action failed";
      toast.error(msg);
    }
  }

  function handleStart(l: LectureResponse) {
    withErrorAlert(startMutation.mutateAsync(l.id));
  }
  function handleComplete(l: LectureResponse) {
    withErrorAlert(completeMutation.mutateAsync(l.id));
  }
  function handleCancel(l: LectureResponse) {
    withErrorAlert(cancelMutation.mutateAsync(l.id));
  }
  function handleDeleteClick(l: LectureResponse) {
    setDeleteTarget(l);
  }
  async function handleDeleteConfirm() {
    if (!deleteTarget) return;
    await deleteMutation.mutateAsync(deleteTarget.id);
  }
  function handleSubstitute(l: LectureResponse) {
    setSubstituteTarget(l);
    setSubstituteOpen(true);
  }
  async function handleSubstituteSubmit(data: LectureSubstitute) {
    if (!substituteTarget) return;
    await substituteMutation.mutateAsync({
      lectureId: substituteTarget.id,
      data,
    });
  }
  function handleNoShow(l: LectureResponse) {
    setNoShowTarget(l);
    setNoShowOpen(true);
  }
  async function handleNoShowSubmit(data: LectureNoShow) {
    if (!noShowTarget) return;
    await noShowMutation.mutateAsync({
      lectureId: noShowTarget.id,
      data,
    });
  }
  function handleGenerateDpp(l: LectureResponse) {
    setDppTarget(l);
    setDppOpen(true);
  }
  function handleRecordMakeup(l: LectureResponse) {
    setMakeupPrefillId(l.id);
    setMakeupOpen(true);
  }
  function handleActuals(l: LectureResponse) {
    setActualsTarget(l);
    setActualsOpen(true);
  }
  async function handleActualsSubmit(lectureId: string, data: LectureActuals) {
    await actualsMutation.mutateAsync({ lectureId, data });
  }

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  function toggleAllVisible(checked: boolean) {
    setSelectedIds(checked ? new Set(filtered.map((l) => l.id)) : new Set());
  }
  async function handleCopySelected() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    const target = copyTargetDate || tomorrowIso();
    try {
      const res = await copySelectedMutation.mutateAsync({
        lectureIds: ids,
        targetDate: target,
      });
      setSelectedIds(new Set());
      setCopyTargetDate("");
      const summary =
        `Copied ${res.copied} lecture(s) to ${res.target_date}` +
        (res.skipped ? ` · ${res.skipped} skipped` : "") +
        ".";
      toast.success(summary, res.errors.slice(0, 6).join(" · ") || undefined);
    } catch (err: any) {
      toast.error(
        err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          "Copy failed"
      );
    }
  }
  async function handleDeleteSelectedConfirm() {
    const ids = Array.from(selectedIds);
    for (const id of ids) {
      try {
        await deleteMutation.mutateAsync(id);
      } catch {
        // keep going — partial delete is better than aborting mid-way
      }
    }
    setSelectedIds(new Set());
  }

  const hasFilter = !!(
    debouncedSearch ||
    filterBatchId ||
    filterTeacherId ||
    filterStatus ||
    fromDate ||
    toDate
  );

  function clearFilters() {
    setSearch("");
    setFilterBatchId("");
    setFilterTeacherId("");
    setFilterStatus("");
    setFromDate("");
    setToDate("");
  }

  // CSV of whatever the admin is currently looking at (filters/search applied).
  const visibleLectures = isMsa ? msaFiltered : filtered;
  function handleDownloadCsv() {
    downloadScheduleCsv(visibleLectures, {
      batches,
      teachers,
      subjects: allSubjects,
      topics: allTopics,
      classrooms,
    });
  }

  const headerActions = (
    <div className="flex flex-wrap items-center gap-2">
      {/* Occasional setup/admin tools, collapsed behind one overflow so the two
          everyday actions stay prominent. */}
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button type="button" variant="outline">
              Manage
              <span aria-hidden className="ml-1 text-xs">
                ⌄
              </span>
            </Button>
          }
        />
        <DropdownMenuContent>
          <DropdownMenuItem onClick={() => setTool("timetable")}>
            Weekly timetable
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setTool("holidays")}>
            Holidays
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setTool("leave")}>
            Teacher leave
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setTool("copy")}>
            Copy to next day
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => {
              setMakeupPrefillId(null);
              setMakeupOpen(true);
            }}
          >
            Record makeup
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={handleDownloadCsv}
            disabled={visibleLectures.length === 0}
          >
            Download CSV
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Primary actions */}
      <ImportScheduleDialog branchId={branchId} />
      <CreateLectureDialog
        branchId={branchId}
        batches={batches}
        classrooms={classrooms}
        onSubmit={handleCreate}
        isPending={createMutation.isPending}
      />

      {/* Controlled tool dialogs — no visible trigger; opened from "Manage". */}
      <TimetableDialog
        branchId={branchId}
        batches={batches}
        teachers={teachers}
        classrooms={classrooms}
        hideTrigger
        open={tool === "timetable"}
        onOpenChange={(o) => setTool(o ? "timetable" : null)}
      />
      <HolidaysDialog
        branchId={branchId}
        hideTrigger
        open={tool === "holidays"}
        onOpenChange={(o) => setTool(o ? "holidays" : null)}
      />
      <TeacherLeaveDialog
        branchId={branchId}
        teachers={teachers}
        hideTrigger
        open={tool === "leave"}
        onOpenChange={(o) => setTool(o ? "leave" : null)}
      />
      <CopyScheduleDialog
        branchId={branchId}
        hideTrigger
        open={tool === "copy"}
        onOpenChange={(o) => setTool(o ? "copy" : null)}
      />
    </div>
  );

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Lectures</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {isCalendar
              ? "Week-at-a-glance grid of every batch's scheduled lectures."
              : isMsa
                ? "Schedule, attendance, and one-click DPP generation off completed lectures."
                : "Schedule, run, and track lectures. Backend rejects teacher/batch/classroom conflicts at create time."}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {[
              { key: "full", label: "Full", href: "/lectures" },
              { key: "msa", label: "Simplified", href: "/lectures?view=msa" },
              {
                key: "calendar",
                label: "Calendar",
                href: "/lectures?view=calendar",
              },
            ].map((v, i) => {
              const active =
                (v.key === "full" && !isMsa && !isCalendar) ||
                (v.key === "msa" && isMsa) ||
                (v.key === "calendar" && isCalendar);
              return (
                <span key={v.key}>
                  {i > 0 && " · "}
                  {active ? (
                    <span className="font-medium text-foreground">
                      {v.label}
                    </span>
                  ) : (
                    <Link href={v.href} className="underline">
                      {v.label}
                    </Link>
                  )}
                </span>
              );
            })}
          </p>
        </div>
        {headerActions}
      </div>

      {isCalendar ? (
        <CalendarWeekView
          lectures={calendarQuery.data ?? []}
          batches={batches}
          teachers={teachers}
          subjects={allSubjects}
          weekStart={weekStart}
          onPrev={() => setWeekStart((w) => addDaysDate(w, -7))}
          onNext={() => setWeekStart((w) => addDaysDate(w, 7))}
          onToday={() => setWeekStart(startOfWeekMonday(new Date()))}
          isLoading={calendarQuery.isLoading}
        />
      ) : isMsa ? (
        <>
          {/* MSA KPI strip */}
          <Card size="sm">
            <div className="grid grid-cols-2 gap-3 px-3 sm:grid-cols-4">
              <Kpi label="This week" value={String(msaKpis.thisWeek)} />
              <Kpi label="Completed" value={String(msaKpis.completed)} />
              <Kpi label="Live now" value={String(msaKpis.live)} />
              <Kpi label="Upcoming today" value={String(msaKpis.upcomingToday)} />
            </div>
          </Card>

          {/* Segmented status chips + search */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div
              role="tablist"
              aria-label="Status"
              className="inline-flex flex-wrap gap-1 rounded-lg border bg-muted/40 p-1"
            >
              {MSA_GROUPS.map((g) => {
                const active = msaGroup === g.value;
                return (
                  <button
                    key={g.value}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => setMsaGroup(g.value)}
                    className={
                      "rounded-md px-3 py-1 text-xs font-medium transition-colors " +
                      (active
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground")
                    }
                  >
                    {g.label}
                  </button>
                );
              })}
            </div>
            <span className="flex-1" />
            <Input
              placeholder="Search teacher, batch, topic…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full sm:max-w-xs"
              aria-label="Search lectures"
            />
            <span className="text-xs text-muted-foreground">
              {msaFiltered.length} lecture{msaFiltered.length !== 1 ? "s" : ""}
            </span>
          </div>

          {/* MSA Content */}
          {lecturesQuery.isLoading ? (
            <p className="text-muted-foreground text-sm">Loading lectures...</p>
          ) : lecturesQuery.isError ? (
            <p className="text-destructive text-sm">
              Failed to load lectures. Make sure the backend is running.
            </p>
          ) : msaFiltered.length === 0 ? (
            <LectureEmptyState hasFilter={!!debouncedSearch || msaGroup !== "all"} />
          ) : (
            <LectureTableMsa
              lectures={msaFiltered}
              batches={batches}
              teachers={teachers}
              subjects={allSubjects}
              topics={allTopics}
              onStart={handleStart}
              onComplete={handleComplete}
              onGenerateDpp={handleGenerateDpp}
              onRecordMakeup={handleRecordMakeup}
            />
          )}
        </>
      ) : (
        <>
          {/* At-a-glance strip — week context + the two triage queues that the
              worklists below let you act on. Queue tiles glow when non-empty. */}
          <Card size="sm">
            <div className="grid grid-cols-2 gap-3 px-3 sm:grid-cols-3 xl:grid-cols-6">
              <Kpi label="This week" value={String(msaKpis.thisWeek)} />
              <Kpi
                label="Completed"
                value={String(msaKpis.completed)}
                hint="this week"
                tone="success"
              />
              <Kpi
                label="Live now"
                value={String(msaKpis.live)}
                tone={msaKpis.live > 0 ? "primary" : "default"}
              />
              <Kpi
                label="Pending close-out"
                value={String(pendingActuals.length)}
                tone={pendingActuals.length > 0 ? "warning" : "default"}
              />
              <Kpi
                label="Makeup queue"
                value={String(pendingMakeups.length)}
                tone={pendingMakeups.length > 0 ? "warning" : "default"}
              />
              {(() => {
                const cov = dppCoverageQuery.data;
                const done = cov?.completed ?? 0;
                const withDpp = cov?.with_dpp ?? 0;
                const pct = done > 0 ? Math.round((withDpp / done) * 100) : 0;
                return (
                  <Kpi
                    label="DPP coverage"
                    value={done > 0 ? `${pct}%` : "—"}
                    hint={
                      done > 0
                        ? `${withDpp} of ${done} completed`
                        : "no completed lectures yet"
                    }
                    tone="primary"
                  />
                );
              })()}
            </div>
          </Card>

          {/* End-of-day worklist — past lectures not yet closed out */}
          <PendingActualsPanel
            lectures={pendingActuals}
            batches={batches}
            teachers={teachers}
            subjects={allSubjects}
            onActuals={handleActuals}
          />

          {/* Makeup queue — cancelled / no-show lectures not yet rescheduled */}
          <MakeupQueuePanel
            lectures={pendingMakeups}
            batches={batches}
            teachers={teachers}
            subjects={allSubjects}
            onRecordMakeup={handleRecordMakeup}
          />

          {/* Filters toolbar */}
          <Card size="sm">
            <div className="flex flex-col gap-3 px-3 lg:flex-row lg:flex-wrap lg:items-center">
              <Input
                placeholder="Search by batch or teacher..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full lg:max-w-xs"
              />
              <select
                value={filterBatchId}
                onChange={(e) => setFilterBatchId(e.target.value)}
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
                value={filterTeacherId}
                onChange={(e) => setFilterTeacherId(e.target.value)}
                className={SELECT_CLASS}
                aria-label="Filter by teacher"
              >
                <option value="">All teachers</option>
                {teachers.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.first_name} {t.last_name}
                  </option>
                ))}
              </select>
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className={SELECT_CLASS}
                aria-label="Filter by status"
              >
                <option value="">All statuses</option>
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <Input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="w-full lg:w-40"
                aria-label="From date"
              />
              <Input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="w-full lg:w-40"
                aria-label="To date"
              />
              <span className="flex-1" />
              {hasFilter && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={clearFilters}
                  className="text-muted-foreground"
                >
                  Clear filters
                </Button>
              )}
              <span className="text-sm text-muted-foreground tabular-nums">
                {filtered.length} lecture{filtered.length !== 1 ? "s" : ""}
              </span>
            </div>
          </Card>

          {/* Selection action bar — copy the ticked lectures to a chosen date */}
          {selectedIds.size > 0 && (
            <div className="flex flex-col gap-3 rounded-lg border border-primary/40 bg-primary/5 px-3 py-2 sm:flex-row sm:items-center">
              <span className="text-sm font-medium">
                {selectedIds.size} selected
              </span>
              <span className="flex-1" />
              <label className="flex items-center gap-2 text-sm">
                Copy to
                <Input
                  type="date"
                  value={copyTargetDate}
                  onChange={(e) => setCopyTargetDate(e.target.value)}
                  className="w-40"
                  aria-label="Copy selected to date"
                  placeholder={tomorrowIso()}
                />
              </label>
              <Button
                type="button"
                onClick={handleCopySelected}
                disabled={copySelectedMutation.isPending}
              >
                {copySelectedMutation.isPending
                  ? "Copying…"
                  : `Copy ${selectedIds.size} to ${copyTargetDate || "tomorrow"}`}
              </Button>
              <Button
                type="button"
                variant="destructive"
                onClick={() => setDeleteSelectedOpen(true)}
                disabled={deleteMutation.isPending}
              >
                Delete {selectedIds.size}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setSelectedIds(new Set())}
              >
                Clear
              </Button>
            </div>
          )}

          {/* Content */}
          {lecturesQuery.isLoading ? (
            <p className="text-muted-foreground text-sm">Loading lectures...</p>
          ) : lecturesQuery.isError ? (
            <p className="text-destructive text-sm">
              Failed to load lectures. Make sure the backend is running.
            </p>
          ) : filtered.length === 0 ? (
            <LectureEmptyState hasFilter={hasFilter} />
          ) : (
            <LectureTable
              lectures={filtered}
              batches={batches}
              teachers={teachers}
              subjects={allSubjects}
              topics={allTopics}
              classrooms={classrooms}
              coveredLectureIds={coveredLectureIds}
              selectedIds={selectedIds}
              onToggleSelect={toggleSelect}
              onToggleAll={toggleAllVisible}
              onStart={handleStart}
              onComplete={handleComplete}
              onCancel={handleCancel}
              onDelete={handleDeleteClick}
              onSubstitute={handleSubstitute}
              onNoShow={handleNoShow}
              onActuals={handleActuals}
              onGenerateDpp={handleGenerateDpp}
              onRecordMakeup={handleRecordMakeup}
            />
          )}

          <SessionList
            sessions={sessions}
            batches={batches}
            teachers={teachers}
            subjects={allSubjects}
          />

          <TeacherProductivityPanel
            branchId={branchId}
            fromDate={fromDate}
            toDate={toDate}
          />
        </>
      )}

      <RecordMakeupDialog
        branchId={branchId}
        batches={batches}
        teachers={teachers}
        classrooms={classrooms}
        lectures={lectures}
        onSubmit={handleRecordSession}
        isPending={sessionMutation.isPending}
        open={makeupOpen}
        onOpenChange={(o) => {
          setMakeupOpen(o);
          if (!o) setMakeupPrefillId(null);
        }}
        prefillLectureId={makeupPrefillId}
      />

      <EndOfDayDialog
        branchId={branchId}
        lecture={actualsTarget}
        open={actualsOpen}
        onOpenChange={(o) => {
          setActualsOpen(o);
          if (!o) setActualsTarget(null);
        }}
        onSubmit={handleActualsSubmit}
        isPending={actualsMutation.isPending}
      />

      <GenerateDppModal
        lecture={dppTarget}
        batches={batches}
        subjects={allSubjects}
        topics={allTopics}
        open={dppOpen}
        onOpenChange={(o) => {
          setDppOpen(o);
          if (!o) setDppTarget(null);
        }}
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

      <MarkSubstituteDialog
        lecture={substituteTarget}
        teachers={teachers}
        allLectures={lectures}
        branchId={branchId}
        open={substituteOpen}
        onOpenChange={(o) => {
          setSubstituteOpen(o);
          if (!o) setSubstituteTarget(null);
        }}
        onSubmit={handleSubstituteSubmit}
        isPending={substituteMutation.isPending}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title="Delete lecture?"
        description="This soft-deletes the lecture. Attendance records remain in the database."
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteConfirm}
      />

      <ConfirmDialog
        open={deleteSelectedOpen}
        onOpenChange={setDeleteSelectedOpen}
        title={`Delete ${selectedIds.size} selected lecture(s)?`}
        description="This soft-deletes the selected lectures. Attendance records remain in the database."
        confirmLabel={`Delete ${selectedIds.size}`}
        destructive
        onConfirm={handleDeleteSelectedConfirm}
      />
    </div>
  );
}

const KPI_VALUE_TONE: Record<string, string> = {
  default: "text-foreground",
  success: "text-emerald-600 dark:text-emerald-400",
  primary: "text-primary",
  warning: "text-amber-600 dark:text-amber-500",
};

function Kpi({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "success" | "primary" | "warning";
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`text-xl font-semibold tabular-nums ${KPI_VALUE_TONE[tone]}`}>
        {value}
      </span>
      {hint && <span className="text-[10px] text-muted-foreground">{hint}</span>}
    </div>
  );
}
