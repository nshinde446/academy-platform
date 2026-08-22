import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  NotificationSettings,
  NotificationSettingsUpdate,
  NotificationTemplate,
  NotificationTemplateUpdate,
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

export const notificationTemplateKeys = {
  all: ["notification-templates"] as const,
  list: (branchId: string) =>
    [...notificationTemplateKeys.all, branchId] as const,
};

export function useNotificationTemplates(branchId: string | undefined) {
  return useQuery<NotificationTemplate[]>({
    queryKey: notificationTemplateKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<NotificationTemplate[]>(
        "/api/v1/notifications/templates",
        { params: { branch_id: branchId, limit: 200 } },
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useUpdateNotificationTemplate(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: NotificationTemplateUpdate;
    }) => {
      const res = await apiClient.patch<NotificationTemplate>(
        `/api/v1/notifications/templates/${id}`,
        data,
      );
      return res.data;
    },
    onSuccess: () => {
      if (branchId) {
        queryClient.invalidateQueries({
          queryKey: notificationTemplateKeys.list(branchId),
        });
      }
    },
  });
}
