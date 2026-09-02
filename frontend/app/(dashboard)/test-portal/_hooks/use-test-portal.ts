import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  RankList,
  ScheduleTestInput,
  TestSummary,
  UploadResultSummary,
} from "../_schemas/test-portal";

export const testPortalKeys = {
  all: ["test-portal"] as const,
  tests: (branchId: string) => [...testPortalKeys.all, "tests", branchId] as const,
  ranklist: (branchId: string, testId: string) =>
    [...testPortalKeys.all, "ranklist", branchId, testId] as const,
};

// Scheduled tests for the branch (paper_type TEST included). Filtered client-side
// to the OMR test-portal tests.
export function useTests(branchId: string | undefined) {
  return useQuery<TestSummary[]>({
    queryKey: testPortalKeys.tests(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<TestSummary[]>("/api/v1/tests", {
        params: { branch_id: branchId, limit: 200 },
      });
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useScheduleTest(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: ScheduleTestInput) => {
      const res = await apiClient.post<TestSummary>("/api/v1/tests", {
        ...data,
        paper_type: "TEST",
      });
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        qc.invalidateQueries({ queryKey: testPortalKeys.tests(branchId) });
      }
    },
  });
}

export function useUploadResult(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ testId, file }: { testId: string; file: File }) => {
      const form = new FormData();
      form.append("file", file);
      const res = await apiClient.post<UploadResultSummary>(
        `/api/v1/tests/${testId}/upload-result`,
        form,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    onSuccess: (_data, vars) => {
      if (branchId) {
        qc.invalidateQueries({
          queryKey: testPortalKeys.ranklist(branchId, vars.testId),
        });
      }
    },
  });
}

export function useRankList(branchId: string | undefined, testId: string | undefined) {
  return useQuery<RankList>({
    queryKey: testPortalKeys.ranklist(branchId!, testId!),
    queryFn: async () => {
      const res = await apiClient.get<RankList>(
        `/api/v1/tests/${testId}/ranklist`,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    enabled: !!branchId && !!testId,
  });
}

// Download the rank list (PDF / Excel) as a blob and save it.
export function useDownloadRankList(branchId: string | undefined) {
  return useMutation({
    mutationFn: async ({ testId, format }: { testId: string; format: "pdf" | "xlsx" }) => {
      const res = await apiClient.get(`/api/v1/tests/${testId}/ranklist/download`, {
        params: { branch_id: branchId, format },
        responseType: "blob",
      });
      const cd = res.headers["content-disposition"] as string | undefined;
      const match = cd?.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] ?? `rank-list.${format}`;
      const url = URL.createObjectURL(res.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
  });
}
