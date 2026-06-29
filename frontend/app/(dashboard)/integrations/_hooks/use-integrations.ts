import { useMutation, useQuery } from "@tanstack/react-query";
import apiClient from "@/services/api-client";

export interface EtoStatus {
  enabled: boolean;
  configured: boolean;
  base_url: string;
  lookback_days: number;
  default_branch_id: string | null;
}

export interface EtoPullResult {
  rows: number;
  events: number;
  inserted: number;
  skipped_no_student: number;
  skipped_duplicate: number;
  days_rebuilt: number;
  from_date: string;
  to_date: string;
}

// eTimeOffice integration status (config presence only — no secrets).
export function useEtoStatus() {
  return useQuery<EtoStatus>({
    queryKey: ["integrations", "etimeoffice", "status"],
    queryFn: async () => {
      const res = await apiClient.get<EtoStatus>(
        "/api/v1/attendance/etimeoffice/status",
      );
      return res.data;
    },
  });
}

// Admin-triggered manual pull for a date range.
export function useEtoPull(branchId: string | undefined) {
  return useMutation({
    mutationFn: async ({ start, end }: { start: string; end: string }) => {
      const res = await apiClient.post<EtoPullResult>(
        "/api/v1/attendance/etimeoffice/pull",
        undefined,
        { params: { branch_id: branchId, start, end } },
      );
      return res.data;
    },
  });
}
