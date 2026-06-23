import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  StudentResponse,
  StudentCreate,
  StudentStatsPage,
  StudentUpdate,
  StudentWithStats,
  StudentTestHistoryRow,
  StudentTopicMastery,
  StudentUpcomingTest,
  ImportJob,
  AcademicYearResponse,
} from "../_schemas/student";

export interface RosterParams {
  offset: number;
  limit: number;
  search: string;
  sortBy?: string;
  order?: "asc" | "desc";
  standard?: string;
  targetExam?: string;
  feesStatus?: string;
  batchId?: string;
}

export const studentKeys = {
  all: ["students"] as const,
  list: (branchId: string) => [...studentKeys.all, "list", branchId] as const,
  withStats: (branchId: string) =>
    [...studentKeys.all, "with-stats", branchId] as const,
  roster: (branchId: string) =>
    [...studentKeys.all, "roster", branchId] as const,
  detail: (branchId: string, id: string) =>
    [...studentKeys.all, "detail", branchId, id] as const,
  testHistory: (branchId: string, id: string) =>
    [...studentKeys.all, "test-history", branchId, id] as const,
  topicMastery: (branchId: string, id: string) =>
    [...studentKeys.all, "topic-mastery", branchId, id] as const,
  upcomingTests: (branchId: string, id: string) =>
    [...studentKeys.all, "upcoming-tests", branchId, id] as const,
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
// Full branch roster — used where the whole set is needed (attendance batch
// roster, a student's batch-rank context). The paginated table uses
// useStudentsRoster instead.
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

// One page of the roster (server-side paginated/searched/sorted).
export function useStudentsRoster(
  branchId: string | undefined,
  params: RosterParams
) {
  return useQuery<StudentStatsPage>({
    queryKey: [...studentKeys.roster(branchId!), params],
    queryFn: async () => {
      const res = await apiClient.get<StudentStatsPage>(
        "/api/v1/students/roster",
        {
          params: {
            branch_id: branchId,
            offset: params.offset,
            limit: params.limit,
            search: params.search || undefined,
            sort_by: params.sortBy,
            order: params.order,
            standard: params.standard || undefined,
            target_exam: params.targetExam || undefined,
            fees_status: params.feesStatus || undefined,
            batch_id: params.batchId || undefined,
          },
        }
      );
      return res.data;
    },
    enabled: !!branchId,
    // Keep the current page visible while the next one loads (no flicker).
    placeholderData: keepPreviousData,
  });
}

// Polls a background import job until it finishes, for the progress bar.
export function useImportJob(
  branchId: string | undefined,
  jobId: string | null,
) {
  return useQuery<ImportJob>({
    queryKey: ["students", "import-job", branchId ?? "", jobId ?? ""],
    queryFn: async () => {
      const res = await apiClient.get<ImportJob>(
        `/api/v1/students/import/jobs/${jobId}`,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    enabled: !!branchId && !!jobId,
    // Poll while the job is still running; stop once it's done.
    refetchInterval: (query) => {
      const s = query.state.data?.job_status;
      return s === "completed" || s === "failed" ? false : 800;
    },
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
        queryClient.invalidateQueries({
          queryKey: studentKeys.roster(branchId),
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
        queryClient.invalidateQueries({
          queryKey: studentKeys.roster(branchId),
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
        queryClient.invalidateQueries({
          queryKey: studentKeys.roster(branchId),
        });
      }
    },
  });
}

export interface BulkUpdatePayload {
  student_ids: string[];
  fees_status?: string | null;
  standard?: string | null;
  stream?: string | null;
  batch_id?: string | null;
}

// Apply one field change to a set of selected students (roster bulk actions).
export function useBulkUpdateStudents(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: BulkUpdatePayload) => {
      const res = await apiClient.post<{ updated: number }>(
        "/api/v1/students/bulk-update",
        payload,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: studentKeys.withStats(branchId),
        });
        queryClient.invalidateQueries({ queryKey: studentKeys.roster(branchId) });
      }
    },
  });
}

// Soft-deletes a selected set of students.
export function useBulkDeleteStudents(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (studentIds: string[]) => {
      const res = await apiClient.post<{ deleted: number }>(
        "/api/v1/students/bulk-delete",
        { student_ids: studentIds },
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: studentKeys.withStats(branchId),
        });
        queryClient.invalidateQueries({ queryKey: studentKeys.roster(branchId) });
      }
    },
  });
}

// Soft-deletes every student in the branch (keeps batches/courses/curriculum).
export function useDeleteAllStudents(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<{ deleted: number }>(
        "/api/v1/students/delete-all",
        null,
        { params: { branch_id: branchId, confirm: true } },
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({ queryKey: studentKeys.list(branchId) });
        queryClient.invalidateQueries({
          queryKey: studentKeys.withStats(branchId),
        });
        queryClient.invalidateQueries({
          queryKey: studentKeys.roster(branchId),
        });
      }
    },
  });
}

export function useStudentTestHistory(
  branchId: string | undefined,
  studentId: string,
) {
  return useQuery<StudentTestHistoryRow[]>({
    queryKey: studentKeys.testHistory(branchId!, studentId),
    queryFn: async () => {
      const res = await apiClient.get<StudentTestHistoryRow[]>(
        `/api/v1/students/${studentId}/test-history`,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    enabled: !!branchId && !!studentId,
  });
}

export function useStudentTopicMastery(
  branchId: string | undefined,
  studentId: string,
) {
  return useQuery<StudentTopicMastery[]>({
    queryKey: studentKeys.topicMastery(branchId!, studentId),
    queryFn: async () => {
      const res = await apiClient.get<StudentTopicMastery[]>(
        `/api/v1/students/${studentId}/topic-mastery`,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    enabled: !!branchId && !!studentId,
  });
}

export function useStudentUpcomingTests(
  branchId: string | undefined,
  studentId: string,
) {
  return useQuery<StudentUpcomingTest[]>({
    queryKey: studentKeys.upcomingTests(branchId!, studentId),
    queryFn: async () => {
      const res = await apiClient.get<StudentUpcomingTest[]>(
        `/api/v1/students/${studentId}/upcoming-tests`,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    enabled: !!branchId && !!studentId,
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
