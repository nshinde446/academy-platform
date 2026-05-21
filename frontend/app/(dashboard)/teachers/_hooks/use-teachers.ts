import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  TeacherResponse,
  TeacherCreate,
  TeacherUpdate,
} from "../_schemas/teacher";

export const teacherKeys = {
  all: ["teachers"] as const,
  list: (branchId: string) => [...teacherKeys.all, "list", branchId] as const,
  detail: (branchId: string, id: string) =>
    [...teacherKeys.all, "detail", branchId, id] as const,
};

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
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: teacherKeys.list(branchId) });
      }
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
      }
    },
  });
}
