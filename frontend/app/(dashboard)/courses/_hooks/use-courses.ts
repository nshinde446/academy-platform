import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  AcademicYearResponse,
  CourseCreate,
  CourseResponse,
} from "../_schemas/course";

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

export function useCreateCourse(
  branchId: string | undefined,
  academicYearId: string | undefined
) {
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
      if (branchId && academicYearId) {
        queryClient.invalidateQueries({
          queryKey: courseKeys.list(branchId, academicYearId),
        });
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
