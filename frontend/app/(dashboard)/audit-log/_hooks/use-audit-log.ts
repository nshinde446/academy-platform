import { useQuery } from "@tanstack/react-query";
import apiClient from "@/services/api-client";

export interface AuditLogItem {
  id: string;
  user_id: string | null;
  action: string;
  table_name: string;
  record_id: string;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  timestamp: string;
  ip_address: string | null;
  branch_id: string | null;
}

export interface AuditLogListResponse {
  items: AuditLogItem[];
  total: number;
}

export interface AuditLogFilters {
  userId: string;
  tableName: string;
  action: string;
}

export function useAuditLog(filters: AuditLogFilters, offset: number, limit: number) {
  return useQuery<AuditLogListResponse>({
    queryKey: ["audit-log", filters, offset, limit],
    queryFn: async () => {
      const res = await apiClient.get<AuditLogListResponse>("/api/v1/audit/logs", {
        params: {
          ...(filters.userId ? { user_id: filters.userId } : {}),
          ...(filters.tableName ? { table_name: filters.tableName } : {}),
          ...(filters.action ? { action: filters.action } : {}),
          offset,
          limit,
        },
      });
      return res.data;
    },
  });
}
