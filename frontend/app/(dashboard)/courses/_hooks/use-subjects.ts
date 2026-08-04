import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  SubjectResponse,
  SubjectSeedRequest,
  SubjectSeedResponse,
  SyllabusOption,
} from "../_schemas/subject";

// Root matches the lectures module's subjectKeys.all ("subjects"), so seeding /
// adding / deleting here also refreshes the Schedule-Lecture subject dropdown.
export const subjectKeys = {
  all: ["subjects"] as const,
  byCourse: (branchId: string, courseId: string) =>
    [...subjectKeys.all, "by-course", branchId, courseId] as const,
};

export function useCourseSubjects(
  branchId: string | undefined,
  courseId: string | undefined
) {
  return useQuery<SubjectResponse[]>({
    queryKey: subjectKeys.byCourse(branchId!, courseId!),
    queryFn: async () => {
      const res = await apiClient.get<SubjectResponse[]>(
        "/api/v1/academic/subjects",
        { params: { branch_id: branchId, course_id: courseId } }
      );
      return res.data;
    },
    enabled: !!branchId && !!courseId,
  });
}

export function useSyllabi() {
  return useQuery<SyllabusOption[]>({
    queryKey: ["syllabi"],
    queryFn: async () => {
      const res = await apiClient.get<SyllabusOption[]>("/api/v1/academic/syllabi");
      return res.data;
    },
    staleTime: Infinity, // static presets
  });
}

export function useSeedSubjects(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: SubjectSeedRequest) => {
      const res = await apiClient.post<SubjectSeedResponse>(
        "/api/v1/academic/subjects/seed",
        body
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: subjectKeys.all });
    },
  });
}

export function useCreateSubject(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      course_id: string;
      academic_year_id: string;
      name: string;
      code: string;
    }) => {
      const res = await apiClient.post<SubjectResponse>(
        "/api/v1/academic/subjects",
        { ...body, branch_id: branchId }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: subjectKeys.all });
    },
  });
}

export function useDeleteSubject(branchId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (subjectId: string) => {
      await apiClient.delete(`/api/v1/academic/subjects/${subjectId}`, {
        params: { branch_id: branchId },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: subjectKeys.all });
    },
  });
}
