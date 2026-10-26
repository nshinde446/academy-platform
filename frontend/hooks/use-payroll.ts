import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";

// ── types (mirror backend payroll schemas) ──────────────────────────────────

export interface PayrollConfig {
  payroll_enabled: boolean;
  holiday_treatment: string;
  allow_half_day: boolean;
  carry_forward_cap: number;
  carry_forward_expiry_months: number;
  allow_payout: boolean;
  allow_negative_balance: boolean;
  unapproved_shortfall: string;
  request_raiser_roles: string[];
  request_approver_role: string;
  allow_manager_approver: boolean;
  prorate_on_join_leave: boolean;
  prorate_rounding: number;
}

export interface Holiday {
  id: string;
  holiday_date: string;
  title: string;
  kind: string;
  credit_days: number;
}

export interface MonthSettings {
  year: number;
  month: number;
  required_days: number;
  lifecycle: "OPEN" | "CLOSED" | "LOCKED" | "NOT_SET";
  notes: string | null;
  holidays: Holiday[];
}

export interface ReportRow {
  staff_id: string;
  emp_code: string;
  name: string;
  department: string;
  required_days: number;
  present_days: number;
  half_days: number;
  paid_leave_days: number;
  net_days: number;
  balance_in: number;
  balance_out: number;
  uncovered_days: number;
  deferred_days: number;
  late_fine_total: number;
}

export interface ReportResponse {
  year: number;
  month: number;
  lifecycle: string;
  rows: ReportRow[];
  totals: {
    staff_count: number;
    present_days: number;
    uncovered_days: number;
    late_fine_total: number;
  };
}

export interface LedgerRow {
  year: number;
  month: number;
  seq: number;
  entry_type: string;
  days: number;
  running_balance: number;
  note: string | null;
  created_by: string | null;
  created_at: string | null;
}

export interface LedgerResponse {
  staff_id: string;
  emp_code: string;
  name: string;
  current_balance: number;
  rows: LedgerRow[];
}

export interface ExtraDayRequestDto {
  id: string;
  staff_id: string;
  source_year: number;
  source_month: number;
  target_year: number;
  target_month: number;
  shortfall_days: number;
  request_status: "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED" | "EXPIRED";
  requested_by: string;
  decided_by: string | null;
  note: string | null;
}

export const payrollKeys = {
  all: ["payroll"] as const,
  config: () => [...payrollKeys.all, "config"] as const,
  months: (b: string, y?: number) => [...payrollKeys.all, "months", b, y ?? "all"] as const,
  month: (b: string, y: number, m: number) => [...payrollKeys.all, "month", b, y, m] as const,
  report: (b: string, y: number, m: number, d?: string, s?: string) =>
    [...payrollKeys.all, "report", b, y, m, d ?? "", s ?? ""] as const,
  ledger: (b: string, s: string) => [...payrollKeys.all, "ledger", b, s] as const,
  requests: (b: string, status?: string) =>
    [...payrollKeys.all, "requests", b, status ?? "all"] as const,
};

// ── config ───────────────────────────────────────────────────────────────────

export function usePayrollConfig(enabled = true) {
  return useQuery<PayrollConfig>({
    queryKey: payrollKeys.config(),
    queryFn: async () => (await apiClient.get<PayrollConfig>("/api/v1/payroll/config")).data,
    enabled,
  });
}

/**
 * Whether payroll is switched on (the module is dormant until then). Pass
 * `active = false` to skip the fetch entirely (e.g. for roles that never see
 * payroll), in which case it resolves to false.
 */
export function usePayrollEnabled(active = true): boolean {
  const { data } = usePayrollConfig(active);
  return active && !!data?.payroll_enabled;
}

export interface DepartmentLite {
  id: string;
  name: string;
}

/** Departments for the report filter (reuses the staff module's endpoint). */
export function usePayrollDepartments(branchId: string | undefined) {
  return useQuery<DepartmentLite[]>({
    queryKey: [...payrollKeys.all, "departments", branchId ?? ""],
    queryFn: async () =>
      (await apiClient.get<DepartmentLite[]>("/api/v1/staff/departments", {
        params: { branch_id: branchId },
      })).data,
    enabled: !!branchId,
  });
}

export function useUpdatePayrollConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (changes: Partial<PayrollConfig>) =>
      (await apiClient.put<PayrollConfig>("/api/v1/payroll/config", changes)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: payrollKeys.all }),
  });
}

// ── month setup ───────────────────────────────────────────────────────────────

export function useMonth(branchId: string | undefined, year: number, month: number) {
  return useQuery<MonthSettings>({
    queryKey: payrollKeys.month(branchId!, year, month),
    queryFn: async () =>
      (await apiClient.get<MonthSettings>(`/api/v1/payroll/months/${year}/${month}`, {
        params: { branch_id: branchId },
      })).data,
    enabled: !!branchId,
  });
}

export function useMonths(branchId: string | undefined, year?: number) {
  return useQuery<MonthSettings[]>({
    queryKey: payrollKeys.months(branchId!, year),
    queryFn: async () =>
      (await apiClient.get<MonthSettings[]>("/api/v1/payroll/months", {
        params: { branch_id: branchId, year },
      })).data,
    enabled: !!branchId,
  });
}

export function useUpsertMonth(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { year: number; month: number; required_days: number; notes?: string | null; reason?: string | null }) =>
      (await apiClient.put<MonthSettings>(`/api/v1/payroll/months/${v.year}/${v.month}`, {
        required_days: v.required_days, notes: v.notes ?? null, reason: v.reason ?? null,
      }, { params: { branch_id: branchId } })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: payrollKeys.all }),
  });
}

export function useAddHoliday(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { year: number; month: number; holiday_date: string; title: string; kind: string; credit_days: number }) =>
      (await apiClient.post<MonthSettings>(`/api/v1/payroll/months/${v.year}/${v.month}/holidays`, {
        holiday_date: v.holiday_date, title: v.title, kind: v.kind, credit_days: v.credit_days,
      }, { params: { branch_id: branchId } })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: payrollKeys.all }),
  });
}

export function useRemoveHoliday(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { year: number; month: number; holidayId: string }) =>
      (await apiClient.delete<MonthSettings>(
        `/api/v1/payroll/months/${v.year}/${v.month}/holidays/${v.holidayId}`,
        { params: { branch_id: branchId } },
      )).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: payrollKeys.all }),
  });
}

export function useMonthLifecycle(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { year: number; month: number; verb: "close" | "lock" | "reopen"; reason?: string | null }) =>
      (await apiClient.post<MonthSettings>(`/api/v1/payroll/months/${v.year}/${v.month}/${v.verb}`, {
        reason: v.reason ?? null,
      }, { params: { branch_id: branchId } })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: payrollKeys.all }),
  });
}

// ── report + ledger ────────────────────────────────────────────────────────────

export function usePayrollReport(
  branchId: string | undefined,
  year: number,
  month: number,
  departmentId?: string,
  staffId?: string,
) {
  return useQuery<ReportResponse>({
    queryKey: payrollKeys.report(branchId!, year, month, departmentId, staffId),
    queryFn: async () =>
      (await apiClient.get<ReportResponse>("/api/v1/payroll/report", {
        params: {
          branch_id: branchId, year, month,
          department_id: departmentId || undefined, staff_id: staffId || undefined,
        },
      })).data,
    enabled: !!branchId,
  });
}

export function useLedger(branchId: string | undefined, staffId: string | undefined) {
  return useQuery<LedgerResponse>({
    queryKey: payrollKeys.ledger(branchId!, staffId!),
    queryFn: async () =>
      (await apiClient.get<LedgerResponse>(`/api/v1/payroll/staff/${staffId}/ledger`, {
        params: { branch_id: branchId },
      })).data,
    enabled: !!branchId && !!staffId,
  });
}

/** Trigger a browser download of the report or ledger export. */
export async function downloadPayroll(path: string, params: Record<string, string>) {
  const qs = new URLSearchParams(params).toString();
  const res = await apiClient.get(`${path}?${qs}`, { responseType: "blob" });
  const disposition = res.headers["content-disposition"] as string | undefined;
  const filename = disposition?.match(/filename="?([^"]+)"?/)?.[1] ?? "payroll";
  const url = window.URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
