import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  AcademicYearCreate,
  AcademicYearResponse,
} from "../_schemas/academic-year";

export const academicYearKeys = {
  all: ["academic-years"] as const,
  list: (branchId: string) =>
    [...academicYearKeys.all, "list", branchId] as const,
};

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
    mutationFn: async (data: AcademicYearCreate) => {
      const res = await apiClient.post<AcademicYearResponse>(
        "/api/v1/academic/academic-years",
        data
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

export function useDeleteAcademicYear(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (yearId: string) => {
      await apiClient.delete(
        `/api/v1/academic/academic-years/${yearId}`,
        { params: { branch_id: branchId } }
      );
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
