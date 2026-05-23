"use client";

import { useMemo, useState } from "react";
import { useQueries } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import { useUserStore } from "@/store/user-store";
import { useDebounce } from "@/hooks/use-debounce";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  subjectKeys,
  topicKeys,
  useBatchesForLectures,
  useCancelLecture,
  useCompleteLecture,
  useCreateLecture,
  useCreateLectureSession,
  useDeleteLecture,
  useLectures,
  useLectureSessions,
  useMarkNoShow,
  useMarkSubstitute,
  useStartLecture,
  useClassrooms,
  useTeachers,
} from "./_hooks/use-lectures";
import type {
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
import { LectureEmptyState } from "./_components/lecture-empty-state";
import { CreateLectureDialog } from "./_components/create-lecture-dialog";
import { MarkSubstituteDialog } from "./_components/mark-substitute-dialog";
import { MarkNoShowDialog } from "./_components/mark-no-show-dialog";
import { RecordMakeupDialog } from "./_components/record-makeup-dialog";
import { MergeLecturesDialog } from "./_components/merge-lectures-dialog";
import { SessionList } from "./_components/session-list";

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

export default function LecturesPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);
  const [filterBatchId, setFilterBatchId] = useState("");
  const [filterTeacherId, setFilterTeacherId] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

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
  const [alertMessage, setAlertMessage] = useState<string | null>(null);

  const lecturesQuery = useLectures(branchId);
  const sessionsQuery = useLectureSessions(branchId);
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

  const batches = batchesQuery.data ?? [];
  const teachers = teachersQuery.data ?? [];
  const classrooms = classroomsQuery.data ?? [];
  const lectures = lecturesQuery.data ?? [];
  const sessions = sessionsQuery.data ?? [];

  // Resolve all subjects/topics referenced by the visible lectures so the
  // table can render their names. Group lectures by the (batch.course_id,
  // subject_id) they reference, then load. To keep this dashboard simple,
  // we fetch subjects per unique course on-page and topics per unique subject.
  const uniqueCourseIds = useMemo(() => {
    const set = new Set<string>();
    for (const l of lectures) {
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
  }, [lectures, sessions, batches]);

  const uniqueSubjectIds = useMemo(() => {
    const set = new Set<string>();
    for (const l of lectures) set.add(l.subject_id);
    for (const s of sessions) set.add(s.subject_id);
    return Array.from(set);
  }, [lectures, sessions]);

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
      setAlertMessage(msg);
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

  const hasFilter = !!(
    debouncedSearch ||
    filterBatchId ||
    filterTeacherId ||
    filterStatus ||
    fromDate ||
    toDate
  );

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Lectures</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Schedule, run, and track lectures. Backend rejects teacher/batch/
            classroom conflicts at create time.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <MergeLecturesDialog
            batches={batches}
            teachers={teachers}
            classrooms={classrooms}
            lectures={lectures}
            onSubmit={handleRecordSession}
            isPending={sessionMutation.isPending}
          />
          <RecordMakeupDialog
            branchId={branchId}
            batches={batches}
            teachers={teachers}
            classrooms={classrooms}
            lectures={lectures}
            onSubmit={handleRecordSession}
            isPending={sessionMutation.isPending}
          />
          <CreateLectureDialog
            branchId={branchId}
            batches={batches}
            teachers={teachers}
            classrooms={classrooms}
            onSubmit={handleCreate}
            isPending={createMutation.isPending}
          />
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-center">
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
        <span className="text-sm text-muted-foreground">
          {filtered.length} lecture{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

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
          coveredLectureIds={coveredLectureIds}
          onStart={handleStart}
          onComplete={handleComplete}
          onCancel={handleCancel}
          onDelete={handleDeleteClick}
          onSubstitute={handleSubstitute}
          onNoShow={handleNoShow}
        />
      )}

      <SessionList
        sessions={sessions}
        batches={batches}
        teachers={teachers}
        subjects={allSubjects}
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
        open={!!alertMessage}
        onOpenChange={(o) => !o && setAlertMessage(null)}
        title="Action failed"
        description={alertMessage ?? ""}
        confirmLabel="OK"
        hideCancel
      />
    </div>
  );
}
