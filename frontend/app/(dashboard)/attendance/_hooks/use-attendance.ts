import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import { studentKeys } from "../../students/_hooks/use-students";
import type {
  AttendanceMarkRequest,
  AttendanceRecord,
  AttendanceSummary,
  BatchMatrix,
  BranchSummaryRow,
  ClassroomRegisterRow,
  DailyAttendance,
  DayStatus,
  DefaulterRow,
} from "../_schemas/attendance";

// Live-view refresh cadence. Punches reach the DB within a couple of minutes
// (SmartOffice/eTimeOffice poll) or seconds (BioMax push); polling the read
// models keeps the on-screen register/timeline current without a manual reload.
// react-query pauses these while the tab is backgrounded (refetchIntervalIn-
// Background defaults to false), so an idle tab costs nothing.
const LIVE_REGISTER_MS = 12_000;
const LIVE_TIMELINE_MS = 30_000;

export const attendanceKeys = {
  all: ["attendance"] as const,
  lecture: (branchId: string, lectureId: string) =>
    [...attendanceKeys.all, "lecture", branchId, lectureId] as const,
  register: (branchId: string, batchId: string, day: string) =>
    [...attendanceKeys.all, "register", branchId, batchId, day] as const,
  timeline: (branchId: string, studentId: string, start: string, end: string) =>
    [...attendanceKeys.all, "timeline", branchId, studentId, start, end] as const,
  summary: (branchId: string, studentId: string, start: string, end: string) =>
    [...attendanceKeys.all, "summary", branchId, studentId, start, end] as const,
  defaulters: (branchId: string, start: string, end: string, threshold: number) =>
    [...attendanceKeys.all, "defaulters", branchId, start, end, threshold] as const,
  branchSummary: (branchId: string, start: string, end: string) =>
    [...attendanceKeys.all, "branch-summary", branchId, start, end] as const,
  matrix: (branchId: string, batchId: string, start: string, end: string) =>
    [...attendanceKeys.all, "matrix", branchId, batchId, start, end] as const,
};

// Classroom day register (Reference B) — P/A roster for a batch on one day,
// computed from biometric day-attendance.
export function useClassroomRegister(
  branchId: string | undefined,
  batchId: string | undefined,
  day: string | undefined,
) {
  return useQuery<ClassroomRegisterRow[]>({
    queryKey: attendanceKeys.register(branchId!, batchId!, day!),
    queryFn: async () => {
      const res = await apiClient.get<ClassroomRegisterRow[]>(
        "/api/v1/attendance/daily/register",
        { params: { branch_id: branchId, batch_id: batchId, day } },
      );
      return res.data;
    },
    enabled: !!branchId && !!batchId && !!day,
    refetchInterval: LIVE_REGISTER_MS,
  });
}

// One student's day-by-day IN/OUT/status timeline (Reference A).
export function useStudentTimeline(
  branchId: string | undefined,
  studentId: string | undefined,
  start: string,
  end: string,
) {
  return useQuery<DailyAttendance[]>({
    queryKey: attendanceKeys.timeline(branchId!, studentId!, start, end),
    queryFn: async () => {
      const res = await apiClient.get<DailyAttendance[]>(
        `/api/v1/attendance/daily/student/${studentId}`,
        { params: { branch_id: branchId, start, end } },
      );
      return res.data;
    },
    enabled: !!branchId && !!studentId && !!start && !!end,
    refetchInterval: LIVE_TIMELINE_MS,
  });
}

// Students below an attendance threshold over a range, worst-first — the
// defaulter board (surfaces the 75% eligibility rule).
export function useDefaulters(
  branchId: string | undefined,
  start: string,
  end: string,
  threshold: number,
) {
  return useQuery<DefaulterRow[]>({
    queryKey: attendanceKeys.defaulters(branchId!, start, end, threshold),
    queryFn: async () => {
      const res = await apiClient.get<DefaulterRow[]>(
        "/api/v1/attendance/daily/defaulters",
        { params: { branch_id: branchId, start, end, threshold } },
      );
      return res.data;
    },
    enabled: !!branchId && !!start && !!end,
  });
}

// Register matrix for one batch over a range — students × working-day columns,
// each cell P/L/A, with per-student % and per-day present totals.
export function useBatchMatrix(
  branchId: string | undefined,
  batchId: string | undefined,
  start: string,
  end: string,
) {
  return useQuery<BatchMatrix>({
    queryKey: attendanceKeys.matrix(branchId!, batchId!, start, end),
    queryFn: async () => {
      const res = await apiClient.get<BatchMatrix>(
        "/api/v1/attendance/daily/matrix",
        { params: { branch_id: branchId, batch_id: batchId, start, end } },
      );
      return res.data;
    },
    enabled: !!branchId && !!batchId && !!start && !!end,
    refetchInterval: LIVE_REGISTER_MS,
  });
}

// Per-batch attendance summary over a range — the institute overview. Driven
// with a single day (start == end) for a "today at a glance" snapshot.
export function useBranchSummary(
  branchId: string | undefined,
  start: string,
  end: string,
) {
  return useQuery<BranchSummaryRow[]>({
    queryKey: attendanceKeys.branchSummary(branchId!, start, end),
    queryFn: async () => {
      const res = await apiClient.get<BranchSummaryRow[]>(
        "/api/v1/attendance/daily/branch-summary",
        { params: { branch_id: branchId, start, end } },
      );
      return res.data;
    },
    enabled: !!branchId && !!start && !!end,
    refetchInterval: LIVE_REGISTER_MS,
  });
}

// Download an attendance report (Excel / PDF) as a blob and save it.
export type ReportScope =
  | "student"
  | "batch"
  | "all-batches"
  | "daily-ledger"
  | "day";

export function useDownloadAttendanceReport(branchId: string | undefined) {
  return useMutation({
    mutationFn: async ({
      scope,
      id,
      start,
      end,
      day,
      fmt,
    }: {
      scope: ReportScope;
      id?: string;
      start: string;
      end: string;
      // The single-day report ("day" scope) uses batch_id (`id`) + `day`
      // instead of the start/end range the other scopes take.
      day?: string;
      fmt: "xlsx" | "pdf";
    }) => {
      if (scope === "day") {
        const res = await apiClient.get("/api/v1/attendance/reports/day", {
          params: { branch_id: branchId, batch_id: id, day, fmt },
          responseType: "blob",
        });
        const cd = res.headers["content-disposition"] as string | undefined;
        const match = cd?.match(/filename="?([^"]+)"?/);
        const filename = match?.[1] ?? `attendance-day.${fmt}`;
        const url = URL.createObjectURL(res.data as Blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        return;
      }
      const path =
        scope === "student"
          ? `/api/v1/attendance/reports/student/${id}`
          : scope === "batch"
            ? `/api/v1/attendance/reports/batch/${id}`
            : scope === "daily-ledger"
              ? `/api/v1/attendance/reports/daily-ledger`
              : `/api/v1/attendance/reports/all-batches`;
      const res = await apiClient.get(path, {
        params: { branch_id: branchId, start, end, fmt },
        responseType: "blob",
      });
      // Filename comes from Content-Disposition; fall back to a sane default.
      const cd = res.headers["content-disposition"] as string | undefined;
      const match = cd?.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] ?? `attendance-${scope}.${fmt}`;
      const url = URL.createObjectURL(res.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
  });
}

// Attendance % over a range (working_days = days with >=1 scheduled lecture).
export function useAttendanceSummary(
  branchId: string | undefined,
  studentId: string | undefined,
  start: string,
  end: string,
) {
  return useQuery<AttendanceSummary>({
    queryKey: attendanceKeys.summary(branchId!, studentId!, start, end),
    queryFn: async () => {
      const res = await apiClient.get<AttendanceSummary>(
        `/api/v1/attendance/daily/summary/${studentId}`,
        { params: { branch_id: branchId, start, end } },
      );
      return res.data;
    },
    enabled: !!branchId && !!studentId && !!start && !!end,
  });
}

// Records already marked for a lecture. Students without a record yet are
// simply absent from this list — the page treats them as "not marked".
export function useLectureAttendance(
  branchId: string | undefined,
  lectureId: string | undefined,
) {
  return useQuery<AttendanceRecord[]>({
    queryKey: attendanceKeys.lecture(branchId!, lectureId!),
    queryFn: async () => {
      const res = await apiClient.get<AttendanceRecord[]>(
        `/api/v1/attendance/lecture/${lectureId}`,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    enabled: !!branchId && !!lectureId,
    refetchInterval: LIVE_REGISTER_MS,
  });
}

export function useMarkAttendance(
  branchId: string | undefined,
  lectureId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: AttendanceMarkRequest) => {
      const res = await apiClient.post<AttendanceRecord>(
        `/api/v1/attendance/lecture/${lectureId}/mark`,
        { source: "MANUAL", ...data },
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId && lectureId) {
        queryClient.invalidateQueries({
          queryKey: attendanceKeys.lecture(branchId, lectureId),
        });
        // Per-student attendance % is derived elsewhere; keep it fresh.
        queryClient.invalidateQueries({
          queryKey: studentKeys.withStats(branchId),
        });
      }
    },
  });
}

// Super-admin manual day mark for a student who forgot to scan. Writes a
// MANUAL day row (never overwritten by a later punch sync); refetches the
// register so the "Manually Marked" tag appears immediately.
export function useManualMarkDay(
  branchId: string | undefined,
  batchId: string | undefined,
  day: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { student_id: string; status?: DayStatus }) => {
      const res = await apiClient.post(
        "/api/v1/attendance/daily/mark",
        { student_id: data.student_id, day, status: data.status ?? "PRESENT" },
        { params: { branch_id: branchId } },
      );
      return res.data as DailyAttendance;
    },
    onSuccess: () => {
      if (branchId && batchId && day) {
        queryClient.invalidateQueries({
          queryKey: attendanceKeys.register(branchId, batchId, day),
        });
      }
    },
  });
}

// Queue a parent WhatsApp notification for the selected students on a day.
export function useSendDayNotification(branchId: string | undefined) {
  return useMutation({
    mutationFn: async (data: {
      batch_id: string;
      day: string;
      student_ids: string[];
    }) => {
      const res = await apiClient.post<{ queued: number }>(
        "/api/v1/attendance/daily/notify",
        data,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
  });
}

// Aggregate raw biometric punches into attendance records for a lecture.
// Seeds ABSENT for students with no punch and PRESENT/LATE for those who
// punched. No-ops for students already marked.
export function useProcessPunches(
  branchId: string | undefined,
  lectureId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<AttendanceRecord[]>(
        `/api/v1/attendance/process/${lectureId}`,
        undefined,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId && lectureId) {
        queryClient.invalidateQueries({
          queryKey: attendanceKeys.lecture(branchId, lectureId),
        });
        queryClient.invalidateQueries({
          queryKey: studentKeys.withStats(branchId),
        });
      }
    },
  });
}
