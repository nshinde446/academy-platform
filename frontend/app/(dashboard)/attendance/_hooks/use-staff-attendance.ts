import { useQuery } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type { StaffDayRegisterRow } from "../_schemas/staff-attendance";

// Live-view refresh, matching the student day register — punches reach the DB
// within seconds (BioMax push) / minutes (poll); react-query pauses this while
// the tab is backgrounded.
const LIVE_REGISTER_MS = 12_000;

export const staffAttendanceKeys = {
  all: ["staff-attendance"] as const,
  dayRegister: (branchId: string, day: string, departmentId: string) =>
    [...staffAttendanceKeys.all, "day", branchId, day, departmentId] as const,
};

export function useStaffDayRegister(
  branchId: string | undefined,
  day: string | undefined,
  departmentId?: string,
) {
  return useQuery({
    queryKey: staffAttendanceKeys.dayRegister(
      branchId ?? "",
      day ?? "",
      departmentId ?? "all",
    ),
    queryFn: async () => {
      const { data } = await apiClient.get<StaffDayRegisterRow[]>(
        "/api/v1/staff/day-register",
        {
          params: {
            branch_id: branchId,
            day,
            department_id: departmentId || undefined,
          },
        },
      );
      return data;
    },
    enabled: !!branchId && !!day,
    refetchInterval: LIVE_REGISTER_MS,
  });
}
