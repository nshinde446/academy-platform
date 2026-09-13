import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  NotificationSettings,
  NotificationSettingsUpdate,
  NotificationTemplate,
  NotificationTemplateUpdate,
  WhatsappBatch,
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

export const whatsappBatchKeys = {
  all: ["whatsapp-batches"] as const,
  list: (branchId: string) => [...whatsappBatchKeys.all, branchId] as const,
};

export function useWhatsappBatches(branchId: string | undefined) {
  return useQuery<WhatsappBatch[]>({
    queryKey: whatsappBatchKeys.list(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<WhatsappBatch[]>(
        "/api/v1/notifications/whatsapp-batches",
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useUpdateWhatsappBatches(branchId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (batchIds: string[]) => {
      const res = await apiClient.put<WhatsappBatch[]>(
        "/api/v1/notifications/whatsapp-batches",
        { batch_ids: batchIds },
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    onSuccess: (data) => {
      if (branchId) {
        queryClient.setQueryData(whatsappBatchKeys.list(branchId), data);
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
