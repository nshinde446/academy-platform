import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import { studentKeys } from "../../students/_hooks/use-students";
import type {
  AttendanceMarkRequest,
  AttendanceRecord,
  AttendanceSummary,
  ClassroomRegisterRow,
  DailyAttendance,
} from "../_schemas/attendance";

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
  });
}

// Download an attendance report (Excel / PDF) as a blob and save it.
export type ReportScope = "student" | "batch" | "all-batches";

export function useDownloadAttendanceReport(branchId: string | undefined) {
  return useMutation({
    mutationFn: async ({
      scope,
      id,
      start,
      end,
      fmt,
    }: {
      scope: ReportScope;
      id?: string;
      start: string;
      end: string;
      fmt: "xlsx" | "pdf";
    }) => {
      const path =
        scope === "student"
          ? `/api/v1/attendance/reports/student/${id}`
          : scope === "batch"
            ? `/api/v1/attendance/reports/batch/${id}`
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
