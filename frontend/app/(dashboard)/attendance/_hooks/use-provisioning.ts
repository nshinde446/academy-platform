import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  DeviceCommandRow,
  DeviceStatusResponse,
  ProvisionDevicesResponse,
  ProvisionPlanResponse,
  ProvisionPushResponse,
  ReconcileResponse,
} from "../_schemas/provisioning";

// Live-refresh cadence for the queue while commands are in flight — the device
// drains them on its next contact, so a short poll keeps the status current.
const QUEUE_LIVE_MS = 8_000;

export const provisioningKeys = {
  all: ["provisioning"] as const,
  devices: (branchId: string) =>
    [...provisioningKeys.all, "devices", branchId] as const,
  reconcile: (branchId: string, devId: string) =>
    [...provisioningKeys.all, "reconcile", branchId, devId] as const,
  commands: (branchId: string, devId: string) =>
    [...provisioningKeys.all, "commands", branchId, devId] as const,
  status: (branchId: string, devId: string) =>
    [...provisioningKeys.all, "status", branchId, devId] as const,
};

// The device's own live counts (userCount/faceCount) + last-seen heartbeat, from
// the status block it sends on every poll. Polls so the count stays current.
export function useDeviceStatus(
  branchId: string | undefined,
  devId: string | undefined,
  enabled: boolean,
) {
  return useQuery<DeviceStatusResponse>({
    queryKey: provisioningKeys.status(branchId ?? "", devId ?? ""),
    queryFn: async () => {
      const res = await apiClient.get<DeviceStatusResponse>(
        "/api/v1/attendance/provisioning/device-status",
        { params: { dev_id: devId } },
      );
      return res.data;
    },
    enabled: !!branchId && !!devId && enabled,
    refetchInterval: QUEUE_LIVE_MS,
  });
}

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

// The outbound command queue for a device (pending → sent → confirmed/failed).
// Polls while enabled so the UI reflects the device draining it. Read-only —
// nothing here emits to the device.
export function useDeviceCommands(
  branchId: string | undefined,
  devId: string | undefined,
  enabled: boolean,
) {
  return useQuery<DeviceCommandRow[]>({
    queryKey: provisioningKeys.commands(branchId ?? "", devId ?? ""),
    queryFn: async () => {
      const res = await apiClient.get<DeviceCommandRow[]>(
        "/api/v1/attendance/provisioning/commands",
        { params: { dev_id: devId, limit: 200 } },
      );
      return res.data;
    },
    enabled: !!branchId && !!devId && enabled,
    refetchInterval: QUEUE_LIVE_MS,
  });
}

// Dry-run: what a push WOULD do for an explicit student set. No side effects,
// so it's a mutation we call on demand (not a cached query).
export function useProvisionDryRun(devId: string | undefined) {
  return useMutation<ProvisionPlanResponse, unknown, string[]>({
    mutationFn: async (studentIds: string[]) => {
      const res = await apiClient.post<ProvisionPlanResponse>(
        "/api/v1/attendance/provisioning/dry-run",
        { dev_id: devId, student_ids: studentIds },
      );
      return res.data;
    },
  });
}

// Enqueue register commands for an explicit student set. Idempotent server-side
// (in-flight users are skipped), so a re-run never double-queues. On success we
// refresh both the queue and the reconcile diff.
export function useProvisionPush(
  branchId: string | undefined,
  devId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation<ProvisionPushResponse, unknown, string[]>({
    mutationFn: async (studentIds: string[]) => {
      const res = await apiClient.post<ProvisionPushResponse>(
        "/api/v1/attendance/provisioning/push",
        { dev_id: devId, student_ids: studentIds },
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId && devId) {
        queryClient.invalidateQueries({
          queryKey: provisioningKeys.commands(branchId, devId),
        });
        queryClient.invalidateQueries({
          queryKey: provisioningKeys.reconcile(branchId, devId),
        });
      }
    },
  });
}

// Pull a still-pending command out of the queue. A sent command can't be
// cancelled (the device already has it) — the API 409s and the UI surfaces it.
export function useCancelCommand(
  branchId: string | undefined,
  devId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation<DeviceCommandRow, unknown, string>({
    mutationFn: async (commandId: string) => {
      const res = await apiClient.post<DeviceCommandRow>(
        `/api/v1/attendance/provisioning/commands/${commandId}/cancel`,
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId && devId) {
        queryClient.invalidateQueries({
          queryKey: provisioningKeys.commands(branchId, devId),
        });
      }
    },
  });
}
