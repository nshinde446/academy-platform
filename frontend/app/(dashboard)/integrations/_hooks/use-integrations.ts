import { useMutation, useQuery } from "@tanstack/react-query";
import apiClient from "@/services/api-client";

export interface SmartOfficeStatus {
  enabled: boolean;
  configured: boolean;
  base_url: string;
  lookback_days: number;
  default_branch_id: string | null;
}

export interface SmartOfficePullResult {
  rows: number;
  events: number;
  inserted: number;
  skipped_no_student: number;
  skipped_duplicate: number;
  days_rebuilt: number;
  from_date: string;
  to_date: string;
}

// BioMax SmartOffice integration status (config presence only — no secrets).
export function useSmartOfficeStatus() {
  return useQuery<SmartOfficeStatus>({
    queryKey: ["integrations", "smartoffice", "status"],
    queryFn: async () => {
      const res = await apiClient.get<SmartOfficeStatus>(
        "/api/v1/attendance/smartoffice/status",
      );
      return res.data;
    },
  });
}

// Admin-triggered manual cloud pull for a date range (tests the SmartOffice
// REST API path; the on-prem agent pushes automatically and needs no pull).
export function useSmartOfficePull(branchId: string | undefined) {
  return useMutation({
    mutationFn: async ({ start, end }: { start: string; end: string }) => {
      const res = await apiClient.post<SmartOfficePullResult>(
        "/api/v1/attendance/smartoffice/pull",
        undefined,
        { params: { branch_id: branchId, start, end } },
      );
      return res.data;
    },
  });
}
