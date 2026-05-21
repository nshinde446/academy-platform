import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  BatchSummary,
  ClassroomSummary,
  LectureCreate,
  LectureResponse,
  SubjectSummary,
  TeacherSummary,
  TopicSummary,
} from "../_schemas/lecture";

export const lectureKeys = {
  all: ["lectures"] as const,
  list: (branchId: string) => [...lectureKeys.all, "list", branchId] as const,
};

export const teacherKeys = {
  all: ["teachers"] as const,
  list: (branchId: string) => [...teacherKeys.all, "list", branchId] as const,
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
