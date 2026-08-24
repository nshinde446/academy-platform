import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";

export interface BatchRef {
  id: string;
  name: string;
}

export interface CoordinatorBatches {
  user_id: string;
  batches: BatchRef[];
}

export interface AccountsGrant {
  id: string;
  user_id: string;
  branch_id: string;
  batch_id: string | null;
  batch_name: string | null;
  expires_at: string | null;
  granted_by: string;
  created_at: string;
}

const keys = {
  coordinator: (userId: string) => ["coordinator-batches", userId] as const,
  grants: (userId: string) => ["accounts-grants", userId] as const,
};

export function useCoordinatorBatches(userId: string | undefined) {
  return useQuery<CoordinatorBatches>({
    queryKey: keys.coordinator(userId ?? ""),
    queryFn: async () => {
      const res = await apiClient.get<CoordinatorBatches>(
        `/api/v1/access/coordinators/${userId}/batches`,
      );
      return res.data;
    },
    enabled: !!userId,
  });
}

export function useSetCoordinatorBatches(userId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (batchIds: string[]) => {
      const res = await apiClient.put<CoordinatorBatches>(
        `/api/v1/access/coordinators/${userId}/batches`,
        { batch_ids: batchIds },
      );
      return res.data;
    },
    onSuccess: () => {
      if (userId) {
        qc.invalidateQueries({ queryKey: keys.coordinator(userId) });
      }
    },
  });
}

export function useAccountsGrants(userId: string | undefined) {
  return useQuery<AccountsGrant[]>({
    queryKey: keys.grants(userId ?? "all"),
    queryFn: async () => {
      const res = await apiClient.get<AccountsGrant[]>(
        "/api/v1/access/accounts-grants",
        { params: userId ? { user_id: userId } : {} },
      );
      return res.data;
    },
  });
}

export function useCreateGrant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      user_id: string;
      batch_id: string | null;
      expires_at: string | null;
    }) => {
      const res = await apiClient.post<AccountsGrant>(
        "/api/v1/access/accounts-grants",
        body,
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accounts-grants"] });
    },
  });
}

export function useRevokeGrant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (grantId: string) => {
      await apiClient.delete(`/api/v1/access/accounts-grants/${grantId}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accounts-grants"] });
    },
  });
}
