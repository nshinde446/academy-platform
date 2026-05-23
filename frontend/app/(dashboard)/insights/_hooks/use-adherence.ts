import { useQuery } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type { AdherenceResponse } from "../_schemas/adherence";

export const adherenceKeys = {
  all: ["adherence"] as const,
  range: (branchId: string, from: string, to: string) =>
    [...adherenceKeys.all, branchId, from, to] as const,
};

export function useAdherenceInsights(
  branchId: string | undefined,
  fromIsoDate: string,
  toIsoDate: string
) {
  return useQuery<AdherenceResponse>({
    queryKey: adherenceKeys.range(branchId ?? "", fromIsoDate, toIsoDate),
    queryFn: async () => {
      const params: Record<string, string> = {
        branch_id: branchId!,
      };
      if (fromIsoDate) params.from_date = `${fromIsoDate}T00:00:00`;
      if (toIsoDate) params.to_date = `${toIsoDate}T23:59:59`;
      const res = await apiClient.get<AdherenceResponse>(
        "/api/v1/lectures/insights/adherence",
        { params }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}
