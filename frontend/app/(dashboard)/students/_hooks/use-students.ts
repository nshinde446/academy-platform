import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  StudentResponse,
  StudentCreate,
  StudentUpdate,
  StudentWithStats,
  AcademicYearResponse,
} from "../_schemas/student";

export const studentKeys = {
  all: ["students"] as const,
  list: (branchId: string) => [...studentKeys.all, "list", branchId] as const,
  withStats: (branchId: string) =>
    [...studentKeys.all, "with-stats", branchId] as const,
  detail: (branchId: string, id: string) =>
    [...studentKeys.all, "detail", branchId, id] as const,
};

export const academicYearKeys = {
  all: ["academic-years"] as const,
  list: (branchId: string) =>
    [...academicYearKeys.all, "list", branchId] as const,
};

export function useStudents(branchId: string | undefined) {
  return useQuery<StudentResponse[]>({
    queryKey: studentKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<StudentResponse[]>(
        "/api/v1/students",
        { params: { branch_id: branchId, limit: 200 } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

// Roster + per-student stats for the MSA_Design table layout.
export function useStudentsWithStats(branchId: string | undefined) {
  return useQuery<StudentWithStats[]>({
    queryKey: studentKeys.withStats(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<StudentWithStats[]>(
        "/api/v1/students/with-stats",
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useStudent(branchId: string | undefined, studentId: string) {
  return useQuery<StudentResponse>({
    queryKey: studentKeys.detail(branchId!, studentId),
    queryFn: async () => {
      const res = await apiClient.get<StudentResponse>(
        `/api/v1/students/${studentId}`,
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useCreateStudent(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: StudentCreate) => {
      const res = await apiClient.post<StudentResponse>(
        "/api/v1/students",
        data
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: studentKeys.list(branchId) });
        queryClient.invalidateQueries({
          queryKey: studentKeys.withStats(branchId),
        });
      }
    },
  });
}

export function useUpdateStudent(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      studentId,
      data,
    }: {
      studentId: string;
      data: StudentUpdate;
    }) => {
      const res = await apiClient.patch<StudentResponse>(
        `/api/v1/students/${studentId}`,
        data,
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: studentKeys.list(branchId) });
        queryClient.invalidateQueries({
          queryKey: studentKeys.withStats(branchId),
        });
      }
    },
  });
}

export function useDeleteStudent(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (studentId: string) => {
      await apiClient.delete(`/api/v1/students/${studentId}`, {
        params: { branch_id: branchId },
      });
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: studentKeys.list(branchId) });
        queryClient.invalidateQueries({
          queryKey: studentKeys.withStats(branchId),
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
