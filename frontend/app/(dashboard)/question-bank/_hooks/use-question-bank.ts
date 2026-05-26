import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  QuestionBulkResult,
  QuestionResponse,
  QuestionUpdate,
  ReviewStatus,
} from "../_schemas/question";

export interface QuestionListFilters {
  review_status?: ReviewStatus;
  difficulty?: string;
  search?: string;
  source_prefix?: string;
  subject_id?: string;
}

export const questionKeys = {
  all: ["question-bank"] as const,
  list: (branchId: string, filters: QuestionListFilters) =>
    [...questionKeys.all, "list", branchId, filters] as const,
  count: (branchId: string, filters: QuestionListFilters) =>
    [...questionKeys.all, "count", branchId, filters] as const,
};

function buildParams(branchId: string, filters: QuestionListFilters) {
  const params: Record<string, string | number> = {
    branch_id: branchId,
    limit: 100,
  };
  if (filters.review_status) params.review_status = filters.review_status;
  if (filters.difficulty) params.difficulty = filters.difficulty;
  if (filters.search) params.search = filters.search;
  if (filters.source_prefix) params.source_prefix = filters.source_prefix;
  if (filters.subject_id) params.subject_id = filters.subject_id;
  return params;
}

export function useQuestionList(
  branchId: string | undefined,
  filters: QuestionListFilters,
) {
  return useQuery<QuestionResponse[]>({
    queryKey: questionKeys.list(branchId ?? "", filters),
    queryFn: async () => {
      const res = await apiClient.get<QuestionResponse[]>("/api/v1/questions", {
        params: buildParams(branchId!, filters),
      });
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useQuestionCount(
  branchId: string | undefined,
  filters: QuestionListFilters,
) {
  return useQuery<number>({
    queryKey: questionKeys.count(branchId ?? "", filters),
    queryFn: async () => {
      const res = await apiClient.get<{ count: number }>(
        "/api/v1/questions/count",
        { params: buildParams(branchId!, filters) },
      );
      return res.data.count;
    },
    enabled: !!branchId,
  });
}

export function useUpdateQuestion(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      questionId,
      data,
    }: {
      questionId: string;
      data: QuestionUpdate;
    }) => {
      const res = await apiClient.patch<QuestionResponse>(
        `/api/v1/questions/${questionId}`,
        data,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: questionKeys.all });
    },
  });
}

export function useBulkApprove(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (questionIds: string[]) => {
      const res = await apiClient.post<QuestionBulkResult>(
        "/api/v1/questions/bulk-approve",
        { question_ids: questionIds },
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: questionKeys.all });
    },
  });
}

export function useBulkReject(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (questionIds: string[]) => {
      const res = await apiClient.post<QuestionBulkResult>(
        "/api/v1/questions/bulk-reject",
        { question_ids: questionIds },
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: questionKeys.all });
    },
  });
}
