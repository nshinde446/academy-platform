import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  AcademicYearResponse,
  BatchCreate,
  BatchResponse,
  CourseResponse,
} from "../_schemas/batch";

export const batchKeys = {
  all: ["batches"] as const,
  list: (branchId: string) => [...batchKeys.all, "list", branchId] as const,
};

export const courseKeys = {
  all: ["courses"] as const,
  list: (branchId: string) => [...courseKeys.all, "list", branchId] as const,
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

export function useCreateAcademicYear(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (startYear: number) => {
      const res = await apiClient.post<AcademicYearResponse>(
        "/api/v1/academic/academic-years",
        {
          branch_id: branchId,
          name: `${startYear}-${startYear + 1}`,
          start_year: startYear,
          end_year: startYear + 1,
        }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: academicYearKeys.list(branchId),
        });
      }
    },
  });
}
