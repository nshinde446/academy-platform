import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  CollectionSummary,
  CourseFeeConfig,
  FollowUpDashboard,
  ForecastRange,
  PaymentInput,
  PaymentResult,
  ProfileCreateInput,
  RemarkInput,
  StaffPerformance,
  StudentFeeProfile,
} from "../_schemas/fees";

export const feesKeys = {
  all: ["fees"] as const,
  config: (b: string) => [...feesKeys.all, "config", b] as const,
  profile: (b: string, s: string) => [...feesKeys.all, "profile", b, s] as const,
  followup: (b: string, d: string) => [...feesKeys.all, "followup", b, d] as const,
  forecast: (b: string, f: string, t: string) => [...feesKeys.all, "forecast", b, f, t] as const,
  dashboard: (b: string) => [...feesKeys.all, "dashboard", b] as const,
  batchSummary: (b: string, batch: string) => [...feesKeys.all, "batch", b, batch] as const,
  staff: (b: string, d: string) => [...feesKeys.all, "staff", b, d] as const,
};

interface StudentLite {
  id: string;
  first_name: string;
  last_name: string;
  enrollment_number: string | null;
}

// Students enrolled in a batch (uses the fixed batch_id filter, #146).
export function useStudentsInBatch(branchId: string | undefined, batchId: string | undefined) {
  return useQuery<StudentLite[]>({
    queryKey: [...feesKeys.all, "students", branchId ?? "", batchId ?? ""],
    queryFn: async () =>
      // /students caps limit at 200; a batch never exceeds that.
      (await apiClient.get("/api/v1/students", { params: { branch_id: branchId, batch_id: batchId, limit: 200 } })).data,
    enabled: !!branchId && !!batchId,
  });
}

export function useCourseFees(branchId: string | undefined) {
  return useQuery<CourseFeeConfig[]>({
    queryKey: feesKeys.config(branchId ?? ""),
    queryFn: async () => (await apiClient.get("/api/v1/fees/config", { params: { branch_id: branchId } })).data,
    enabled: !!branchId,
  });
}

export function useSetCourseFee(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { course_name: string; standard_fee: number }) =>
      (await apiClient.post<CourseFeeConfig>("/api/v1/fees/config", body, { params: { branch_id: branchId } })).data,
    onSuccess: () => branchId && qc.invalidateQueries({ queryKey: feesKeys.config(branchId) }),
  });
}

export function useFeeProfile(branchId: string | undefined, studentId: string | undefined) {
  return useQuery<StudentFeeProfile>({
    queryKey: feesKeys.profile(branchId ?? "", studentId ?? ""),
    queryFn: async () =>
      (await apiClient.get(`/api/v1/fees/student/${studentId}`, { params: { branch_id: branchId } })).data,
    enabled: !!branchId && !!studentId,
    retry: false,
  });
}

export function useCreateFeeProfile(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ProfileCreateInput) =>
      (await apiClient.post<StudentFeeProfile>("/api/v1/fees/student", body, { params: { branch_id: branchId } })).data,
    onSuccess: (data) => {
      if (!branchId) return;
      qc.invalidateQueries({ queryKey: feesKeys.profile(branchId, data.student_id) });
      qc.invalidateQueries({ queryKey: feesKeys.all });
    },
  });
}

export function useRecordPayment(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ installmentId, body }: { installmentId: string; body: PaymentInput }) =>
      (await apiClient.post<PaymentResult>(`/api/v1/fees/installment/${installmentId}/pay`, body, {
        params: { branch_id: branchId },
      })).data,
    onSuccess: () => branchId && qc.invalidateQueries({ queryKey: feesKeys.all }),
  });
}

export function useAddRemark(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: RemarkInput) =>
      (await apiClient.post("/api/v1/fees/remark", body, { params: { branch_id: branchId } })).data,
    onSuccess: () => branchId && qc.invalidateQueries({ queryKey: feesKeys.all }),
  });
}

export function useFollowUp(branchId: string | undefined, day: string) {
  return useQuery<FollowUpDashboard>({
    queryKey: feesKeys.followup(branchId ?? "", day),
    queryFn: async () =>
      (await apiClient.get("/api/v1/fees/followup", { params: { branch_id: branchId, day } })).data,
    enabled: !!branchId,
  });
}

export function useForecast(branchId: string | undefined, from: string, to: string, enabled: boolean) {
  return useQuery<ForecastRange>({
    queryKey: feesKeys.forecast(branchId ?? "", from, to),
    queryFn: async () =>
      (await apiClient.get("/api/v1/fees/forecast", { params: { branch_id: branchId, from, to } })).data,
    enabled: !!branchId && enabled,
  });
}

export function useOverallSummary(branchId: string | undefined) {
  return useQuery<CollectionSummary>({
    queryKey: feesKeys.dashboard(branchId ?? ""),
    queryFn: async () =>
      (await apiClient.get("/api/v1/fees/dashboard", { params: { branch_id: branchId } })).data,
    enabled: !!branchId,
  });
}

export function useBatchSummary(branchId: string | undefined, batchId: string | undefined) {
  return useQuery<CollectionSummary>({
    queryKey: feesKeys.batchSummary(branchId ?? "", batchId ?? ""),
    queryFn: async () =>
      (await apiClient.get(`/api/v1/fees/batch/${batchId}/summary`, { params: { branch_id: branchId } })).data,
    enabled: !!branchId && !!batchId,
  });
}

export function useStaffPerformance(branchId: string | undefined, day: string) {
  return useQuery<StaffPerformance>({
    queryKey: feesKeys.staff(branchId ?? "", day),
    queryFn: async () =>
      (await apiClient.get("/api/v1/fees/staff-performance", { params: { branch_id: branchId, day } })).data,
    enabled: !!branchId,
  });
}
