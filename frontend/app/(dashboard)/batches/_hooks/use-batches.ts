import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  BatchResponse,
  BatchCreate,
  CourseResponse,
  AcademicYearResponse,
} from "../_schemas/batch";

export const batchKeys = {
  all: ["batches"] as const,
  list: (branchId: string) => [...batchKeys.all, "list", branchId] as const,
  detail: (branchId: string, id: string) =>
    [...batchKeys.all, "detail", branchId, id] as const,
};

export const courseKeys = {
  all: ["courses"] as const,
  list: (branchId: string, academicYearId: string) =>
    [...courseKeys.all, "list", branchId, academicYearId] as const,
};

export const academicYearKeys = {
  all: ["academic-years"] as const,
  list: (branchId: string) =>
    [...academicYearKeys.all, "list", branchId] as const,
};

export function useBatches(branchId: string | undefined) {
  return useQuery<BatchResponse[]>({
    queryKey: batchKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<BatchResponse[]>("/api/v1/batches", {
        params: { branch_id: branchId, limit: 200 },
      });
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useCreateBatch(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: BatchCreate) => {
      const res = await apiClient.post<BatchResponse>("/api/v1/batches", data);
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: batchKeys.list(branchId) });
      }
    },
  });
}

export function useDeleteBatch(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (batchId: string) => {
      await apiClient.delete(`/api/v1/batches/${batchId}`, {
        params: { branch_id: branchId },
      });
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: batchKeys.list(branchId) });
      }
    },
  });
}

export function useAcademicYears(branchId: string | undefined) {
  return useQuery<AcademicYearResponse[]>({
    queryKey: academicYearKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<AcademicYearResponse[]>(
        "/api/v1/academic/academic-years",
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useCourses(
  branchId: string | undefined,
  academicYearId: string | undefined
) {
  return useQuery<CourseResponse[]>({
    queryKey: courseKeys.list(branchId!, academicYearId!),
    queryFn: async () => {
      const res = await apiClient.get<CourseResponse[]>(
        "/api/v1/academic/courses",
        { params: { branch_id: branchId, academic_year_id: academicYearId } }
      );
      return res.data;
    },
    enabled: !!branchId && !!academicYearId,
  });
}
