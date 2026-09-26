import { useMutation, useQuery } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  ProductivityFilters,
  ProductivitySummaryResponse,
} from "../_schemas/productivity-report";

// FastAPI reads list params as repeated keys (teacher_ids=a&teacher_ids=b). Axios
// defaults to bracketed keys, which FastAPI ignores — force repeated serialization.
const REPEAT_PARAMS = { indexes: null } as const;

const reportKeys = {
  all: ["teacher-productivity-report"] as const,
  report: (branchId: string, f: ProductivityFilters) =>
    [...reportKeys.all, branchId, f] as const,
};

// Shared param builder so the JSON query and the export links stay in sync.
export function reportParams(
  branchId: string | undefined,
  f: ProductivityFilters,
): Record<string, unknown> {
  return {
    branch_id: branchId,
    ...(f.fromDate ? { start: f.fromDate } : {}),
    ...(f.toDate ? { end: f.toDate } : {}),
    ...(f.teacherIds.length ? { teacher_ids: f.teacherIds } : {}),
  };
}

export function useProductivityReport(
  branchId: string | undefined,
  filters: ProductivityFilters,
) {
  return useQuery<ProductivitySummaryResponse>({
    queryKey: reportKeys.report(branchId ?? "", filters),
    queryFn: async () => {
      const res = await apiClient.get<ProductivitySummaryResponse>(
        "/api/v1/staff/faculty-activity/summary-data",
        { params: reportParams(branchId, filters), paramsSerializer: REPEAT_PARAMS },
      );
      return res.data;
    },
    enabled: !!branchId && !!filters.fromDate && !!filters.toDate,
  });
}

// Download the report as Excel or PDF (same filters). Blob → anchor click.
export function useDownloadProductivityReport(branchId: string | undefined) {
  return useMutation({
    mutationFn: async ({
      filters,
      fmt,
    }: {
      filters: ProductivityFilters;
      fmt: "xlsx" | "pdf";
    }) => {
      const res = await apiClient.get(
        "/api/v1/staff/faculty-activity/summary",
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
