import { useMutation, useQuery } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  ProductivityReportFilters,
  ProductivityReportResponse,
} from "../_schemas/productivity-report";

// FastAPI reads list params as repeated keys (batch_ids=a&batch_ids=b). Axios
// defaults to bracketed keys (batch_ids[]=a), which FastAPI ignores — so force
// repeated, index-less serialization on every call that sends the filters.
const REPEAT_PARAMS = { indexes: null } as const;

export interface SubjectOption {
  id: string;
  name: string;
}

const reportKeys = {
  all: ["teacher-productivity-report"] as const,
  report: (branchId: string, f: ProductivityReportFilters) =>
    [...reportKeys.all, branchId, f] as const,
};

// Shared param builder so the JSON query and the export links stay in sync.
export function reportParams(
  branchId: string | undefined,
  f: ProductivityReportFilters,
): Record<string, unknown> {
  return {
    branch_id: branchId,
    ...(f.fromDate ? { from_date: `${f.fromDate}T00:00:00Z` } : {}),
    ...(f.toDate ? { to_date: `${f.toDate}T23:59:59Z` } : {}),
    ...(f.batchIds.length ? { batch_ids: f.batchIds } : {}),
    ...(f.subjectIds.length ? { subject_ids: f.subjectIds } : {}),
    ...(f.teacherIds.length ? { teacher_ids: f.teacherIds } : {}),
  };
}

export function useProductivityReport(
  branchId: string | undefined,
  filters: ProductivityReportFilters,
) {
  return useQuery<ProductivityReportResponse>({
    queryKey: reportKeys.report(branchId ?? "", filters),
    queryFn: async () => {
      const res = await apiClient.get<ProductivityReportResponse>(
        "/api/v1/lectures/productivity/report",
        { params: reportParams(branchId, filters), paramsSerializer: REPEAT_PARAMS },
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

// Download the report as Excel or PDF (same filters). Blob → anchor click,
// matching the attendance report download pattern.
export function useDownloadProductivityReport(branchId: string | undefined) {
  return useMutation({
    mutationFn: async ({
      filters,
      fmt,
    }: {
      filters: ProductivityReportFilters;
      fmt: "xlsx" | "pdf";
    }) => {
      const res = await apiClient.get(
        "/api/v1/lectures/productivity/report/export",
        {
          params: { ...reportParams(branchId, filters), fmt },
          paramsSerializer: REPEAT_PARAMS,
          responseType: "blob",
        },
      );
      const cd = res.headers["content-disposition"] as string | undefined;
      const match = cd?.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] ?? `teacher_productivity.${fmt}`;
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

// All subjects in the branch (course_id omitted) — for the subject filter.
export function useSubjectOptions(branchId: string | undefined) {
  return useQuery<SubjectOption[]>({
    queryKey: ["subject-options", branchId ?? ""],
    queryFn: async () => {
      const res = await apiClient.get<SubjectOption[]>(
        "/api/v1/academic/subjects",
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}
