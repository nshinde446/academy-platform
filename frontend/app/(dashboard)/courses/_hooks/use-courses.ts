import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  CourseCreate,
  CourseResponse,
  CourseUpdate,
} from "../_schemas/course";

export const courseKeys = {
  all: ["courses"] as const,
  list: (branchId: string) => [...courseKeys.all, "list", branchId] as const,
};

export function useCourses(branchId: string | undefined) {
  return useQuery<CourseResponse[]>({
    queryKey: courseKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<CourseResponse[]>(
        "/api/v1/academic/courses",
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useCreateCourse(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CourseCreate) => {
      const res = await apiClient.post<CourseResponse>(
        "/api/v1/academic/courses",
        data
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: courseKeys.list(branchId),
        });
      }
    },
  });
}

export function useUpdateCourse(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      courseId,
      data,
    }: {
      courseId: string;
      data: CourseUpdate;
    }) => {
      const res = await apiClient.patch<CourseResponse>(
        `/api/v1/academic/courses/${courseId}`,
        data,
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: courseKeys.list(branchId),
        });
      }
    },
  });
}

export function useDeleteCourse(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (courseId: string) => {
      await apiClient.delete(`/api/v1/academic/courses/${courseId}`, {
        params: { branch_id: branchId },
      });
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: courseKeys.list(branchId),
        });
      }
    },
  });
}
