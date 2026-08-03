import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  AdminUser,
  RoleOption,
  UserCreate,
  UserUpdate,
} from "../_schemas/users";

export const userKeys = {
  all: ["admin-users"] as const,
  list: () => [...userKeys.all, "list"] as const,
  roles: () => [...userKeys.all, "roles"] as const,
};

export function useAdminUsers(enabled: boolean) {
  return useQuery<AdminUser[]>({
    queryKey: userKeys.list(),
    queryFn: async () => (await apiClient.get<AdminUser[]>("/api/v1/auth/users")).data,
    enabled,
  });
}

export function useRoleOptions(enabled: boolean) {
  return useQuery<RoleOption[]>({
    queryKey: userKeys.roles(),
    queryFn: async () => (await apiClient.get<RoleOption[]>("/api/v1/auth/roles")).data,
    enabled,
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: UserCreate) =>
      (await apiClient.post<AdminUser>("/api/v1/auth/users", data)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.list() }),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: UserUpdate }) =>
      (await apiClient.patch<AdminUser>(`/api/v1/auth/users/${id}`, data)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.list() }),
  });
}

export function useResetUserPassword() {
  return useMutation({
    mutationFn: async ({ id, password }: { id: string; password: string }) =>
      apiClient.post(`/api/v1/auth/users/${id}/reset-password`, { password }),
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => apiClient.delete(`/api/v1/auth/users/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.list() }),
  });
}

export function useChangeOwnPassword() {
  return useMutation({
    mutationFn: async (data: { current_password: string; new_password: string }) =>
      apiClient.post("/api/v1/auth/change-password", data),
  });
}
