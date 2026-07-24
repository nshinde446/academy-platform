import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  BatchSummary,
  ClassroomSummary,
  CopyScheduleSummary,
  CopySelectedSummary,
  LectureActuals,
  LectureReschedule,
  LectureCreate,
  LectureNoShow,
  LectureResponse,
  LectureSessionCreate,
  LectureSessionResponse,
  LectureSubstitute,
  ProductivityResponse,
  SubjectSummary,
  TeacherSummary,
  TopicSummary,
  TimetableSlot,
  TimetableSlotResponse,
  GenerateScheduleSummary,
  HolidayResponse,
  EligibleSubstitute,
  TeacherLeaveResponse,
} from "../_schemas/lecture";

export const lectureKeys = {
  all: ["lectures"] as const,
  list: (branchId: string) => [...lectureKeys.all, "list", branchId] as const,
};

export const pendingActualsKeys = {
  all: ["lectures-pending-actuals"] as const,
  list: (branchId: string) => [...pendingActualsKeys.all, branchId] as const,
};

export const makeupQueueKeys = {
  all: ["lectures-pending-makeups"] as const,
  list: (branchId: string) => [...makeupQueueKeys.all, branchId] as const,
};

export const calendarKeys = {
  all: ["lectures-in-range"] as const,
  range: (branchId: string, from: string, to: string) =>
    [...calendarKeys.all, branchId, from, to] as const,
};

export const sessionKeys = {
  all: ["lecture-sessions"] as const,
  list: (branchId: string) => [...sessionKeys.all, "list", branchId] as const,
};

export const teacherKeys = {
  all: ["teachers"] as const,
  list: (branchId: string) => [...teacherKeys.all, "list", branchId] as const,
  bySubject: (branchId: string, subjectId: string) =>
    [...teacherKeys.all, "by-subject", branchId, subjectId] as const,
};

export const productivityKeys = {
  all: ["lecture-productivity"] as const,
  range: (branchId: string, from: string, to: string) =>
    [...productivityKeys.all, branchId, from, to] as const,
};

export const subjectKeys = {
  all: ["subjects"] as const,
  byCourse: (branchId: string, courseId: string) =>
    [...subjectKeys.all, "by-course", branchId, courseId] as const,
};

export const topicKeys = {
  all: ["topics"] as const,
  bySubject: (branchId: string, subjectId: string) =>
    [...topicKeys.all, "by-subject", branchId, subjectId] as const,
};

export const batchKeys = {
  all: ["batches"] as const,
  list: (branchId: string) => [...batchKeys.all, "list", branchId] as const,
};

export const classroomKeys = {
  all: ["classrooms"] as const,
  list: (branchId: string) => [...classroomKeys.all, "list", branchId] as const,
};

export const timetableKeys = {
  all: ["batch-timetable"] as const,
  byBatch: (branchId: string, batchId: string) =>
    [...timetableKeys.all, branchId, batchId] as const,
};

export const holidayKeys = {
  all: ["holidays"] as const,
  list: (branchId: string) => [...holidayKeys.all, branchId] as const,
};

export const leaveKeys = {
  all: ["teacher-leaves"] as const,
  list: (branchId: string) => [...leaveKeys.all, branchId] as const,
};

export const substituteKeys = {
  all: ["eligible-substitutes"] as const,
  forLecture: (branchId: string, lectureId: string) =>
    [...substituteKeys.all, branchId, lectureId] as const,
};

export function useClassrooms(branchId: string | undefined) {
  return useQuery<ClassroomSummary[]>({
    queryKey: classroomKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<ClassroomSummary[]>(
        "/api/v1/classrooms",
        { params: { branch_id: branchId, limit: 200 } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useLectures(branchId: string | undefined) {
  return useQuery<LectureResponse[]>({
    queryKey: lectureKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<LectureResponse[]>("/api/v1/lectures", {
        params: { branch_id: branchId, limit: 200 },
      });
      return res.data;
    },
    enabled: !!branchId,
  });
}

export interface DppCoverage {
  completed: number;
  with_dpp: number;
}

export function useDppCoverage(branchId: string | undefined) {
  return useQuery<DppCoverage>({
    queryKey: [...lectureKeys.all, "dpp-coverage", branchId] as const,
    queryFn: async () => {
      const res = await apiClient.get<DppCoverage>(
        "/api/v1/lectures/dpp-coverage",
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function usePendingActuals(branchId: string | undefined) {
  return useQuery<LectureResponse[]>({
    queryKey: pendingActualsKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<LectureResponse[]>(
        "/api/v1/lectures/pending-actuals",
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useLecturesInRange(
  branchId: string | undefined,
  fromIso: string,
  toIso: string
) {
  return useQuery<LectureResponse[]>({
    queryKey: calendarKeys.range(branchId!, fromIso, toIso),
    queryFn: async () => {
      const res = await apiClient.get<LectureResponse[]>(
        "/api/v1/lectures/in-range",
        { params: { branch_id: branchId, from_date: fromIso, to_date: toIso } }
      );
      return res.data;
    },
    enabled: !!branchId && !!fromIso && !!toIso,
  });
}

export function usePendingMakeups(branchId: string | undefined) {
  return useQuery<LectureResponse[]>({
    queryKey: makeupQueueKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<LectureResponse[]>(
        "/api/v1/lectures/pending-makeups",
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useCreateLecture(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: LectureCreate) => {
      const res = await apiClient.post<LectureResponse>(
        "/api/v1/lectures",
        data
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: lectureKeys.list(branchId),
        });
      }
    },
  });
}

function statusMutation(
  branchId: string | undefined,
  action: "start" | "complete" | "cancel"
) {
  return async (lectureId: string) => {
    const res = await apiClient.patch<LectureResponse>(
      `/api/v1/lectures/${lectureId}/${action}`,
      undefined,
      { params: { branch_id: branchId } }
    );
    return res.data;
  };
}

export function useStartLecture(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: statusMutation(branchId, "start"),
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: lectureKeys.list(branchId),
        });
      }
    },
  });
}

export function useCompleteLecture(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: statusMutation(branchId, "complete"),
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: lectureKeys.list(branchId),
        });
        queryClient.invalidateQueries({
          queryKey: pendingActualsKeys.list(branchId),
        });
      }
    },
  });
}

export function useMarkNoShow(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      lectureId,
      data,
    }: {
      lectureId: string;
      data: LectureNoShow;
    }) => {
      const res = await apiClient.patch<LectureResponse>(
        `/api/v1/lectures/${lectureId}/no-show`,
        data,
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: lectureKeys.list(branchId),
        });
        queryClient.invalidateQueries({
          queryKey: pendingActualsKeys.list(branchId),
        });
        queryClient.invalidateQueries({
          queryKey: makeupQueueKeys.list(branchId),
        });
      }
    },
  });
}

export function useMarkSubstitute(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      lectureId,
      data,
    }: {
      lectureId: string;
      data: LectureSubstitute;
    }) => {
      const res = await apiClient.patch<LectureResponse>(
        `/api/v1/lectures/${lectureId}/substitute`,
        data,
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: lectureKeys.list(branchId),
        });
        // A substitute on a no-show flips it to completed → leaves the queue.
        queryClient.invalidateQueries({
          queryKey: makeupQueueKeys.list(branchId),
        });
      }
    },
  });
}

export function useCancelLecture(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: statusMutation(branchId, "cancel"),
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: lectureKeys.list(branchId),
        });
        queryClient.invalidateQueries({
          queryKey: pendingActualsKeys.list(branchId),
        });
        queryClient.invalidateQueries({
          queryKey: makeupQueueKeys.list(branchId),
        });
      }
    },
  });
}

export function useDeleteLecture(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (lectureId: string) => {
      await apiClient.delete(`/api/v1/lectures/${lectureId}`, {
        params: { branch_id: branchId },
      });
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: lectureKeys.list(branchId),
        });
      }
    },
  });
}

export function useBatchesForLectures(branchId: string | undefined) {
  return useQuery<BatchSummary[]>({
    queryKey: batchKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<BatchSummary[]>("/api/v1/batches", {
        params: { branch_id: branchId, limit: 200 },
      });
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useTeachers(branchId: string | undefined) {
  return useQuery<TeacherSummary[]>({
    queryKey: teacherKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<TeacherSummary[]>("/api/v1/teachers", {
        params: { branch_id: branchId, limit: 200 },
      });
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useTeachersBySubject(
  branchId: string | undefined,
  subjectId: string | undefined
) {
  return useQuery<TeacherSummary[]>({
    queryKey: teacherKeys.bySubject(branchId!, subjectId!),
    queryFn: async () => {
      const res = await apiClient.get<TeacherSummary[]>(
        "/api/v1/teachers/by-subject",
        { params: { branch_id: branchId, subject_id: subjectId } }
      );
      return res.data;
    },
    enabled: !!branchId && !!subjectId,
  });
}

export function useRescheduleLecture(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      lectureId,
      data,
    }: {
      lectureId: string;
      data: LectureReschedule;
    }) => {
      const res = await apiClient.patch<LectureResponse>(
        `/api/v1/lectures/${lectureId}/reschedule`,
        data,
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: lectureKeys.list(branchId) });
      }
    },
  });
}

export function useUpdateActuals(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      lectureId,
      data,
    }: {
      lectureId: string;
      data: LectureActuals;
    }) => {
      const res = await apiClient.patch<LectureResponse>(
        `/api/v1/lectures/${lectureId}/actuals`,
        data,
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: lectureKeys.list(branchId) });
        queryClient.invalidateQueries({ queryKey: productivityKeys.all });
        queryClient.invalidateQueries({
          queryKey: pendingActualsKeys.list(branchId),
        });
      }
    },
  });
}

export function useCopyToNextDay(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      sourceDate,
      targetDate,
    }: {
      sourceDate: string;
      targetDate?: string;
    }) => {
      const res = await apiClient.post<CopyScheduleSummary>(
        "/api/v1/lectures/copy-to-next-day",
        null,
        {
          params: {
            branch_id: branchId,
            source_date: sourceDate,
            ...(targetDate ? { target_date: targetDate } : {}),
          },
        }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: lectureKeys.list(branchId) });
      }
    },
  });
}

export function useBatchTimetable(
  branchId: string | undefined,
  batchId: string | undefined
) {
  return useQuery<TimetableSlotResponse[]>({
    queryKey: timetableKeys.byBatch(branchId!, batchId!),
    queryFn: async () => {
      const res = await apiClient.get<TimetableSlotResponse[]>(
        "/api/v1/lectures/timetable",
        { params: { branch_id: branchId, batch_id: batchId } }
      );
      return res.data;
    },
    enabled: !!branchId && !!batchId,
  });
}

export function useSetBatchTimetable(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      batchId,
      slots,
    }: {
      batchId: string;
      slots: TimetableSlot[];
    }) => {
      const res = await apiClient.put<TimetableSlotResponse[]>(
        "/api/v1/lectures/timetable",
        { slots },
        { params: { branch_id: branchId, batch_id: batchId } }
      );
      return res.data;
    },
    onSuccess: (_data, { batchId }) => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: timetableKeys.byBatch(branchId, batchId),
        });
      }
    },
  });
}

export function useGenerateSchedule(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      fromDate,
      toDate,
      batchId,
    }: {
      fromDate: string;
      toDate: string;
      batchId?: string;
    }) => {
      const res = await apiClient.post<GenerateScheduleSummary>(
        "/api/v1/lectures/timetable/generate",
        null,
        {
          params: {
            branch_id: branchId,
            from_date: fromDate,
            to_date: toDate,
            ...(batchId ? { batch_id: batchId } : {}),
          },
        }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: lectureKeys.list(branchId) });
        // Refresh the week/calendar grid with the freshly generated lectures.
        queryClient.invalidateQueries({ queryKey: calendarKeys.all });
      }
    },
  });
}

export function useHolidays(branchId: string | undefined) {
  return useQuery<HolidayResponse[]>({
    queryKey: holidayKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<HolidayResponse[]>(
        "/api/v1/lectures/holidays",
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useAddHoliday(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ date, name }: { date: string; name: string }) => {
      const res = await apiClient.post<HolidayResponse>(
        "/api/v1/lectures/holidays",
        { holiday_date: date, name },
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: holidayKeys.list(branchId) });
      }
    },
  });
}

export function useDeleteHoliday(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (holidayId: string) => {
      await apiClient.delete(`/api/v1/lectures/holidays/${holidayId}`, {
        params: { branch_id: branchId },
      });
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: holidayKeys.list(branchId) });
      }
    },
  });
}

export function useEligibleSubstitutes(
  branchId: string | undefined,
  lectureId: string | undefined,
  enabled: boolean
) {
  return useQuery<EligibleSubstitute[]>({
    queryKey: substituteKeys.forLecture(branchId!, lectureId!),
    queryFn: async () => {
      const res = await apiClient.get<EligibleSubstitute[]>(
        `/api/v1/lectures/${lectureId}/eligible-substitutes`,
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: enabled && !!branchId && !!lectureId,
  });
}

export function useTeacherLeaves(branchId: string | undefined) {
  return useQuery<TeacherLeaveResponse[]>({
    queryKey: leaveKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<TeacherLeaveResponse[]>(
        "/api/v1/lectures/teacher-leaves",
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useAddTeacherLeave(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      teacher_id: string;
      start_date: string;
      end_date: string;
      reason?: string | null;
    }) => {
      const res = await apiClient.post<TeacherLeaveResponse>(
        "/api/v1/lectures/teacher-leaves",
        body,
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: leaveKeys.list(branchId) });
      }
    },
  });
}

export function useDeleteTeacherLeave(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (leaveId: string) => {
      await apiClient.delete(`/api/v1/lectures/teacher-leaves/${leaveId}`, {
        params: { branch_id: branchId },
      });
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: leaveKeys.list(branchId) });
      }
    },
  });
}

export function useCopySelected(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      lectureIds,
      targetDate,
    }: {
      lectureIds: string[];
      targetDate: string;
    }) => {
      const res = await apiClient.post<CopySelectedSummary>(
        "/api/v1/lectures/copy-selected",
        { lecture_ids: lectureIds, target_date: targetDate },
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: lectureKeys.list(branchId) });
      }
    },
  });
}

export function useProductivityInsights(
  branchId: string | undefined,
  fromDate: string,
  toDate: string
) {
  return useQuery<ProductivityResponse>({
    queryKey: productivityKeys.range(branchId!, fromDate, toDate),
    queryFn: async () => {
      const res = await apiClient.get<ProductivityResponse>(
        "/api/v1/lectures/insights/productivity",
        {
          params: {
            branch_id: branchId,
            ...(fromDate ? { from_date: `${fromDate}T00:00:00Z` } : {}),
            ...(toDate ? { to_date: `${toDate}T23:59:59Z` } : {}),
          },
        }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useSubjectsByCourse(
  branchId: string | undefined,
  courseId: string | undefined
) {
  return useQuery<SubjectSummary[]>({
    queryKey: subjectKeys.byCourse(branchId!, courseId!),
    queryFn: async () => {
      const res = await apiClient.get<SubjectSummary[]>(
        "/api/v1/academic/subjects",
        { params: { branch_id: branchId, course_id: courseId } }
      );
      return res.data;
    },
    enabled: !!branchId && !!courseId,
  });
}

export function useLectureSessions(branchId: string | undefined) {
  return useQuery<LectureSessionResponse[]>({
    queryKey: sessionKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<LectureSessionResponse[]>(
        "/api/v1/lectures/sessions",
        { params: { branch_id: branchId, limit: 200 } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useCreateLectureSession(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: LectureSessionCreate) => {
      const res = await apiClient.post<LectureSessionResponse>(
        "/api/v1/lectures/sessions",
        data,
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: sessionKeys.list(branchId),
        });
        queryClient.invalidateQueries({
          queryKey: lectureKeys.list(branchId),
        });
        // A makeup session linked to a lecture clears it from the makeup queue.
        queryClient.invalidateQueries({
          queryKey: makeupQueueKeys.list(branchId),
        });
      }
    },
  });
}

export function useTopicsBySubject(
  branchId: string | undefined,
  subjectId: string | undefined
) {
  return useQuery<TopicSummary[]>({
    queryKey: topicKeys.bySubject(branchId!, subjectId!),
    queryFn: async () => {
      const res = await apiClient.get<TopicSummary[]>(
        "/api/v1/academic/topics",
        { params: { branch_id: branchId, subject_id: subjectId } }
      );
      return res.data;
    },
    enabled: !!branchId && !!subjectId,
  });
}
