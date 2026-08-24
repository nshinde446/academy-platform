import { useQuery } from "@tanstack/react-query";
import apiClient from "@/services/api-client";

export interface MyBatch {
  id: string;
  name: string;
}

interface MyBatchesResponse {
  user_id: string;
  batches: MyBatch[];
}

// The caller's own assigned batches (Floor Coordinator scope). Empty for roles
// that aren't batch-scoped. Used to scope batch pickers to exactly what the
// server will allow, so a coordinator never picks a batch they'll be 403'd on.
export function useMyBatches(enabled: boolean) {
  return useQuery<MyBatch[]>({
    queryKey: ["my-batches"],
    queryFn: async () => {
      const res = await apiClient.get<MyBatchesResponse>(
        "/api/v1/access/my-batches",
      );
      return res.data.batches;
    },
    enabled,
  });
}
