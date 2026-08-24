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

export function useDeliveryLog(deliveryStatus: string) {
  const { branchId } = useBranchId();
  return useQuery<DeliveryLogRow[]>({
    queryKey: ["whatsapp-delivery-log", branchId ?? "", deliveryStatus],
    queryFn: async () => {
      const res = await apiClient.get<DeliveryLogRow[]>(
        "/api/v1/notifications/delivery-log",
        {
          params: {
            ...(branchId ? { branch_id: branchId } : {}),
            ...(deliveryStatus ? { delivery_status: deliveryStatus } : {}),
            limit: 200,
          },
        },
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}
