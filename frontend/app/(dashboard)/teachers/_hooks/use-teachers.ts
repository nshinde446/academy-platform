import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  TeacherResponse,
  TeacherCreate,
  TeacherSubjects,
  TeacherUpdate,
  TeacherWithStats,
} from "../_schemas/teacher";

export const teacherKeys = {
  all: ["teachers"] as const,
  list: (branchId: string) => [...teacherKeys.all, "list", branchId] as const,
  withStats: (branchId: string) =>
    [...teacherKeys.all, "with-stats", branchId] as const,
  detail: (branchId: string, id: string) =>
    [...teacherKeys.all, "detail", branchId, id] as const,
  subjectOptions: (branchId: string) =>
    [...teacherKeys.all, "subject-options", branchId] as const,
  subjects: (branchId: string, id: string) =>
    [...teacherKeys.all, "subjects", branchId, id] as const,
};

export function useSubjectOptions(branchId: string | undefined) {
  return useQuery<string[]>({
    queryKey: teacherKeys.subjectOptions(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<string[]>(
        "/api/v1/teachers/subject-options",
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useTeacherSubjects(
  branchId: string | undefined,
  teacherId: string | undefined
) {
  return useQuery<string[]>({
    queryKey: teacherKeys.subjects(branchId!, teacherId!),
    queryFn: async () => {
      const res = await apiClient.get<TeacherSubjects>(
        `/api/v1/teachers/${teacherId}/subjects`,
        { params: { branch_id: branchId } }
      );
      return res.data.subjects;
    },
    enabled: !!branchId && !!teacherId,
  });
}

export function useSetTeacherSubjects(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      teacherId,
      subjects,
    }: {
      teacherId: string;
      subjects: string[];
    }) => {
      const res = await apiClient.put<TeacherSubjects>(
        `/api/v1/teachers/${teacherId}/subjects`,
        { subjects },
        { params: { branch_id: branchId } }
      );
      return res.data.subjects;
    },
    onSuccess: () => {
      // Invalidate the whole teachers namespace so the schedule form's
      // subject-filtered dropdown (teacherKeys.bySubject in the lectures
      // module) refreshes too.
      queryClient.invalidateQueries({ queryKey: teacherKeys.all });
    },
  });
}

export function useTeachers(branchId: string | undefined) {
  return useQuery<TeacherResponse[]>({
    queryKey: teacherKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<TeacherResponse[]>("/api/v1/teachers", {
        params: { branch_id: branchId, limit: 200 },
      });
      return res.data;
    },
    enabled: !!branchId,
  });
}

// Roster + per-teacher adherence + outcome metrics for the MSA_Design
// teachers table.
export function useTeachersWithStats(branchId: string | undefined) {
  return useQuery<TeacherWithStats[]>({
    queryKey: teacherKeys.withStats(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<TeacherWithStats[]>(
        "/api/v1/teachers/with-stats",
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useCreateTeacher(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: TeacherCreate) => {
      const res = await apiClient.post<TeacherResponse>(
        "/api/v1/teachers",
        data
      );
      return res.data;
    },
    onSuccess: () => {
      if (!branchId) return;
      // Whole namespace — a create-with-subjects must refresh the schedule
      // form's subject-filtered teacher dropdown too.
      queryClient.invalidateQueries({ queryKey: teacherKeys.all });
    },
  });
}

export function useUpdateTeacher(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      teacherId,
      data,
    }: {
      teacherId: string;
      data: TeacherUpdate;
    }) => {
      const res = await apiClient.patch<TeacherResponse>(
        `/api/v1/teachers/${teacherId}`,
        data,
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: teacherKeys.list(branchId) });
        queryClient.invalidateQueries({
          queryKey: teacherKeys.withStats(branchId),
        });
      }
    },
  });
}

export function useDeleteTeacher(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (teacherId: string) => {
      await apiClient.delete(`/api/v1/teachers/${teacherId}`, {
        params: { branch_id: branchId },
      });
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: teacherKeys.list(branchId) });
        queryClient.invalidateQueries({
          queryKey: teacherKeys.withStats(branchId),
        });
      }
    },
  });
}

// Bulk soft-delete a selected set of teachers from the roster. Mirrors the
// Students bulk-delete flow (POST /teachers/bulk-delete).
export function useBulkDeleteTeachers(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (teacherIds: string[]) => {
      const res = await apiClient.post<{ deleted: number }>(
        "/api/v1/teachers/bulk-delete",
        { teacher_ids: teacherIds },
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: teacherKeys.list(branchId) });
        queryClient.invalidateQueries({
          queryKey: teacherKeys.withStats(branchId),
        });
      }
    },
  });
}
