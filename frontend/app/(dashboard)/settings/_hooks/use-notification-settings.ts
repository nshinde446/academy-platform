import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  NotificationSettings,
  NotificationSettingsUpdate,
} from "../_schemas/settings";

export const notificationSettingsKeys = {
  all: ["notification-settings"] as const,
  detail: (branchId: string) =>
    [...notificationSettingsKeys.all, branchId] as const,
};

export function useNotificationSettings(branchId: string | undefined) {
  return useQuery<NotificationSettings>({
    queryKey: notificationSettingsKeys.detail(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<NotificationSettings>(
        "/api/v1/notifications/settings",
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useUpdateNotificationSettings(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: NotificationSettingsUpdate) => {
      const res = await apiClient.put<NotificationSettings>(
        "/api/v1/notifications/settings",
        data,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    onSuccess: (data) => {
      if (branchId) {
        queryClient.setQueryData(
          notificationSettingsKeys.detail(branchId),
          data,
        );
      }
    },
  });
}
