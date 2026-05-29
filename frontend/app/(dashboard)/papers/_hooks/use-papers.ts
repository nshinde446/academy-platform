import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type { QuestionResponse } from "@/app/(dashboard)/question-bank/_schemas/question";
import type { AutoPickRequest, PaperType, TestResponse } from "../_schemas/paper";

// ── Reference data ───────────────────────────────────────────────────────

export interface SubjectOption {
  id: string;
  name: string;
  academic_year_id: string;
}

// Distinct-by-name subjects (the table can carry one Subject row per course).
export function useSubjectOptions(branchId: string | undefined) {
  return useQuery<SubjectOption[]>({
    queryKey: ["papers", "subject-options", branchId],
    queryFn: async () => {
      const res = await apiClient.get<SubjectOption[]>(
        "/api/v1/academic/subjects",
        { params: { branch_id: branchId } },
      );
      const seen = new Set<string>();
      const out: SubjectOption[] = [];
      for (const s of res.data) {
        if (seen.has(s.name)) continue;
        seen.add(s.name);
        out.push(s);
      }
      return out;
    },
    enabled: !!branchId,
  });
}

export interface BatchOption {
  id: string;
  name: string;
  code: string;
}

export function useBatchOptions(branchId: string | undefined) {
  return useQuery<BatchOption[]>({
    queryKey: ["papers", "batch-options", branchId],
    queryFn: async () => {
      const res = await apiClient.get<BatchOption[]>("/api/v1/batches", {
        params: { branch_id: branchId, limit: 200 },
      });
      return res.data;
    },
    enabled: !!branchId,
  });
}

// ── Available-questions count (reuses the question-bank count endpoint) ────

export interface CountFilters {
  subject_id?: string;
  class_label?: string;
  exam_type?: string;
  difficulty?: string;
  review_status?: string;
}

export function useAvailableCount(
  branchId: string | undefined,
  filters: CountFilters,
  enabled = true,
) {
  return useQuery<number>({
    queryKey: ["papers", "available-count", branchId, filters],
    queryFn: async () => {
      const params: Record<string, string> = { branch_id: branchId! };
      for (const [k, v] of Object.entries(filters)) {
        if (v) params[k] = v;
      }
      const res = await apiClient.get<{ count: number }>(
        "/api/v1/questions/count",
        { params },
      );
      return res.data.count;
    },
    enabled: !!branchId && enabled,
  });
}

// ── Composer actions ──────────────────────────────────────────────────────

export function useAutoPick(branchId: string | undefined) {
  return useMutation({
    mutationFn: async (body: AutoPickRequest) => {
      const res = await apiClient.post<QuestionResponse[]>(
        "/api/v1/tests/auto-pick",
        body,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
  });
}

export interface CreatePaperInput {
  name: string;
  paper_type: PaperType;
  batch_id: string;
  subject_id: string;
  total_marks: number;
}

// Create the draft Test then attach the picked questions, in order.
export function useSavePaper(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      paper,
      questionIds,
    }: {
      paper: CreatePaperInput;
      questionIds: string[];
    }) => {
      const created = await apiClient.post<TestResponse>(
        "/api/v1/tests",
        paper,
        { params: { branch_id: branchId } },
      );
      const test = created.data;
      if (questionIds.length > 0) {
        await apiClient.post(
          `/api/v1/tests/${test.id}/questions`,
          {
            questions: questionIds.map((id, i) => ({
              question_id: id,
              marks_allocated: 1,
              order: i,
            })),
          },
          { params: { branch_id: branchId } },
        );
      }
      return test;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["papers", "list"] });
    },
  });
}

export type PdfKind = "paper" | "answer-key";

// Fetches the PDF as a blob (so the auth cookie / axios credentials are
// sent) and triggers a browser download.
export function useDownloadPaperPdf(branchId: string | undefined) {
  return useMutation({
    mutationFn: async ({
      testId,
      kind,
      name,
    }: {
      testId: string;
      kind: PdfKind;
      name: string;
    }) => {
      const path = kind === "paper" ? "paper.pdf" : "answer-key.pdf";
      const res = await apiClient.get(`/api/v1/tests/${testId}/${path}`, {
        params: { branch_id: branchId },
        responseType: "blob",
      });
      const url = URL.createObjectURL(res.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${name}-${kind}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
  });
}

export function usePaperList(
  branchId: string | undefined,
  batchId?: string,
) {
  return useQuery<TestResponse[]>({
    queryKey: ["papers", "list", branchId, batchId ?? ""],
    queryFn: async () => {
      const params: Record<string, string | number> = {
        branch_id: branchId!,
        limit: 20,
      };
      if (batchId) params.batch_id = batchId;
      const res = await apiClient.get<TestResponse[]>("/api/v1/tests", {
        params,
      });
      return res.data;
    },
    enabled: !!branchId,
  });
}
