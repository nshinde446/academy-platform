import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";

export interface ProvisionDevice {
  dev_id: string;
}

export interface ProvisionDevicesResponse {
  // Whether BIOMAX_PROVISIONING_ENABLED is on. False = dormant (no push).
  enabled: boolean;
  devices: ProvisionDevice[];
}

export function useProvisionDevices(branchId: string | undefined) {
  return useQuery<ProvisionDevicesResponse>({
    queryKey: ["staff-provision-devices", branchId],
    queryFn: async () => {
      const res = await apiClient.get<ProvisionDevicesResponse>(
        "/api/v1/attendance/provisioning/devices",
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

// Mirrors backend app/modules/attendance/schemas/provisioning_schemas.py
// (Staff* variants). The device userId pushed is the staff emp_code (9xxxx).
export interface StaffPlannedCommand {
  staff_id: string;
  vendor_user_id: string | null;
  name: string | null;
  action: string; // create | update | no_change | skipped
  reason: string | null;
}

export interface StaffProvisionPlanResponse {
  dev_id: string;
  to_create: number;
  to_update: number;
  no_change: number;
  skipped: number;
  commands: StaffPlannedCommand[];
}

export interface StaffProvisionPushResponse {
  dev_id: string;
  enqueued: number;
  skipped: number;
  commands: StaffPlannedCommand[];
}

export function useStaffProvisionDryRun(devId: string | undefined) {
  return useMutation<StaffProvisionPlanResponse, unknown, string[]>({
    mutationFn: async (staffIds: string[]) => {
      const res = await apiClient.post<StaffProvisionPlanResponse>(
        "/api/v1/attendance/provisioning/staff/dry-run",
        { dev_id: devId, staff_ids: staffIds }
      );
      return res.data;
    },
  });
}

export function useStaffProvisionPush(devId: string | undefined) {
  const qc = useQueryClient();
  return useMutation<StaffProvisionPushResponse, unknown, string[]>({
    mutationFn: async (staffIds: string[]) => {
      const res = await apiClient.post<StaffProvisionPushResponse>(
        "/api/v1/attendance/provisioning/staff/push",
        { dev_id: devId, staff_ids: staffIds }
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["staff"] });
    },
  });
}
