import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  ClassroomResponse,
  ClassroomCreate,
  ClassroomUpdate,
} from "../_schemas/classroom";

export const classroomKeys = {
  all: ["classrooms"] as const,
  list: (branchId: string) => [...classroomKeys.all, "list", branchId] as const,
};

export function useClassrooms(branchId: string | undefined) {
  return useQuery<ClassroomResponse[]>({
    queryKey: classroomKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<ClassroomResponse[]>(
        "/api/v1/classrooms",
        { params: { branch_id: branchId, limit: 200 } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useCreateClassroom(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: ClassroomCreate) => {
      const res = await apiClient.post<ClassroomResponse>(
        "/api/v1/classrooms",
        data
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: classroomKeys.list(branchId),
        });
      }
    },
  });
}

export function useUpdateClassroom(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      classroomId,
      data,
    }: {
      classroomId: string;
      data: ClassroomUpdate;
    }) => {
      const res = await apiClient.patch<ClassroomResponse>(
        `/api/v1/classrooms/${classroomId}`,
        data,
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: classroomKeys.list(branchId),
        });
      }
    },
  });
}

export function useDeleteClassroom(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (classroomId: string) => {
      await apiClient.delete(`/api/v1/classrooms/${classroomId}`, {
        params: { branch_id: branchId },
      });
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: classroomKeys.list(branchId),
        });
      }
    },
  });
}
