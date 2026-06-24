import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  BatchSummary,
  ClassroomSummary,
  CopyScheduleSummary,
  LectureActuals,
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
} from "../_schemas/lecture";

export const lectureKeys = {
  all: ["lectures"] as const,
  list: (branchId: string) => [...lectureKeys.all, "list", branchId] as const,
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
