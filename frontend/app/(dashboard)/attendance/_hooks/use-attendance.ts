import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import { studentKeys } from "../../students/_hooks/use-students";
import type {
  AttendanceMarkRequest,
  AttendanceRecord,
} from "../_schemas/attendance";

export const attendanceKeys = {
  all: ["attendance"] as const,
  lecture: (branchId: string, lectureId: string) =>
    [...attendanceKeys.all, "lecture", branchId, lectureId] as const,
};

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
