import { useQuery } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  ProvisionDevicesResponse,
  ReconcileResponse,
} from "../_schemas/provisioning";

export const provisioningKeys = {
  all: ["provisioning"] as const,
  devices: (branchId: string) =>
    [...provisioningKeys.all, "devices", branchId] as const,
  reconcile: (branchId: string, devId: string) =>
    [...provisioningKeys.all, "reconcile", branchId, devId] as const,
};

// Configured devices + whether provisioning is enabled at all. Not gated by the
// enabled flag on the backend, so this call never 503s — it's what lets the UI
// tell "feature off" apart from "no device configured". Admin-only (403 else).
export function useProvisionDevices(branchId: string | undefined) {
  return useQuery<ProvisionDevicesResponse>({
    queryKey: provisioningKeys.devices(branchId ?? ""),
    queryFn: async () => {
      const res = await apiClient.get<ProvisionDevicesResponse>(
        "/api/v1/attendance/provisioning/devices",
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

// Three-way diff between platform students and the device's user mirror. Only
// enabled once we know provisioning is on and a device is selected, so we never
// hit the endpoint's by-design 503.
export function useReconcile(
  branchId: string | undefined,
  devId: string | undefined,
  enabled: boolean,
) {
  return useQuery<ReconcileResponse>({
    queryKey: provisioningKeys.reconcile(branchId ?? "", devId ?? ""),
    queryFn: async () => {
      const res = await apiClient.get<ReconcileResponse>(
        "/api/v1/attendance/provisioning/reconcile",
        { params: { dev_id: devId } },
      );
      return res.data;
    },
    enabled: !!branchId && !!devId && enabled,
  });
}
