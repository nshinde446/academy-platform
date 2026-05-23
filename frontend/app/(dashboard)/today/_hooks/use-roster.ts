import { useQuery } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type { RosterResponse } from "../_schemas/roster";

export const rosterKeys = {
  all: ["roster"] as const,
  day: (branchId: string, isoDate: string) =>
    [...rosterKeys.all, branchId, isoDate] as const,
};

export function useRoster(branchId: string | undefined, isoDate: string) {
  return useQuery<RosterResponse>({
    queryKey: rosterKeys.day(branchId ?? "", isoDate),
    queryFn: async () => {
      const res = await apiClient.get<RosterResponse>(
        "/api/v1/lectures/roster",
        { params: { branch_id: branchId, date: isoDate } },
      );
      return res.data;
    },
    enabled: !!branchId && !!isoDate,
    refetchInterval: 60_000,
  });
}
