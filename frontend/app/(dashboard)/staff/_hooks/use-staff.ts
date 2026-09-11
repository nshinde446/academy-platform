import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  DepartmentWithAllocation,
  StaffCreate,
  StaffResponse,
  StaffUpdate,
} from "../_schemas/staff";

export const staffKeys = {
  all: ["staff"] as const,
  list: (branchId: string, deptId?: string) =>
    [...staffKeys.all, "list", branchId, deptId ?? "all"] as const,
  departments: (branchId: string) =>
    [...staffKeys.all, "departments", branchId] as const,
};

export function useDepartments(branchId: string | undefined) {
  return useQuery<DepartmentWithAllocation[]>({
    queryKey: staffKeys.departments(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<DepartmentWithAllocation[]>(
        "/api/v1/staff/departments",
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useStaff(branchId: string | undefined, departmentId?: string) {
  return useQuery<StaffResponse[]>({
    queryKey: staffKeys.list(branchId!, departmentId),
    queryFn: async () => {
      const res = await apiClient.get<StaffResponse[]>("/api/v1/staff", {
        params: { branch_id: branchId, department_id: departmentId },
      });
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useCreateStaff(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: StaffCreate) => {
      const res = await apiClient.post<StaffResponse>("/api/v1/staff", data, {
        params: { branch_id: branchId },
      });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: staffKeys.all });
    },
  });
}

export function useUpdateStaff(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: StaffUpdate }) => {
      const res = await apiClient.patch<StaffResponse>(
        `/api/v1/staff/${id}`,
        data,
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: staffKeys.all });
    },
  });
}

export function useLinkTeacher(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      teacherId,
    }: {
      id: string;
      teacherId: string | null;
    }) => {
      const res = await apiClient.post<StaffResponse>(
        `/api/v1/staff/${id}/link-teacher`,
        { teacher_id: teacherId },
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: staffKeys.all });
    },
  });
}

export function useDeleteStaff(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/api/v1/staff/${id}`, {
        params: { branch_id: branchId },
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: staffKeys.all });
    },
  });
}

export function useBulkDeleteStaff(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (staffIds: string[]) => {
      const res = await apiClient.post<{ deleted: number }>(
        "/api/v1/staff/bulk-delete",
        { staff_ids: staffIds },
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: staffKeys.all });
    },
  });
}
