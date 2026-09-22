import { useQuery } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import { useBranchId } from "@/store/user-store";

export interface DeliveryLogRow {
  id: string;
  student_name: string | null;
  prn: string | null;
  parent_contact: string;
  date: string | null;
  delivery_status: string; // SENT / FAILED / PENDING
  sent_by: string | null; // manual / auto
  sent_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface DeliveryLogFilters {
  deliveryStatus: string;
  batchId: string;
  dateFrom: string; // YYYY-MM-DD
  dateTo: string; // YYYY-MM-DD
  q: string;
}

export function useDeliveryLog(filters: DeliveryLogFilters) {
  const { branchId } = useBranchId();
  const { deliveryStatus, batchId, dateFrom, dateTo, q } = filters;
  return useQuery<DeliveryLogRow[]>({
    queryKey: [
      "whatsapp-delivery-log",
      branchId ?? "",
      deliveryStatus,
      batchId,
      dateFrom,
      dateTo,
      q,
    ],
    queryFn: async () => {
      const res = await apiClient.get<DeliveryLogRow[]>(
        "/api/v1/notifications/delivery-log",
        {
          params: {
            ...(branchId ? { branch_id: branchId } : {}),
            ...(deliveryStatus ? { delivery_status: deliveryStatus } : {}),
            ...(batchId ? { batch_id: batchId } : {}),
            ...(dateFrom ? { date_from: dateFrom } : {}),
            ...(dateTo ? { date_to: dateTo } : {}),
            ...(q.trim() ? { q: q.trim() } : {}),
            limit: 200,
          },
        },
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}
