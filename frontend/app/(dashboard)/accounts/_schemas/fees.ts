// Accounts / Fees module — TS types mirroring the backend fees schemas.

export const PAYMENT_MODES = ["CASH", "UPI", "CHEQUE", "BANK_TRANSFER"] as const;
export const PAYMENT_MODE_LABELS: Record<string, string> = {
  CASH: "Cash",
  UPI: "UPI",
  CHEQUE: "Cheque",
  BANK_TRANSFER: "Bank transfer",
};

export interface CourseFeeConfig {
  id: string;
  branch_id: string;
  course_name: string;
  standard_fee: number;
}

export interface Installment {
  id: string;
  installment_number: number;
  due_date: string;
  amount: number;
  installment_status: "PENDING" | "PAID" | "OVERDUE" | "PARTIAL";
  paid_amount: number;
  paid_date: string | null;
  payment_mode: string | null;
}

export interface Remark {
  id: string;
  student_id: string;
  profile_id: string;
  remark_text: string;
  call_date: string;
  next_followup_date: string | null;
  created_by: string | null;
}

export interface StudentFeeProfile {
  id: string;
  student_id: string;
  branch_id: string;
  batch_id: string;
  actual_fee: number;
  agreed_fee: number;
  discount_amount: number;
  payment_mode: "ONE_TIME" | "INSTALLMENT";
  total_paid: number;
  total_pending: number;
  admission_date: string;
  installments: Installment[];
  remarks: Remark[];
}

export interface ProfileCreateInput {
  student_id: string;
  batch_id: string;
  actual_fee: number;
  agreed_fee: number;
  payment_mode: "ONE_TIME" | "INSTALLMENT";
  admission_date: string;
  first_installment?: number | null;
  remaining_installments?: number | null;
  interval_months?: number;
}

export interface PaymentInput {
  amount_paid: number;
  payment_date: string;
  payment_mode: string;
  notes?: string | null;
}

export interface PaymentResult {
  installment: Installment;
  total_paid: number;
  total_pending: number;
}

export interface RemarkInput {
  student_id: string;
  profile_id: string;
  remark_text: string;
  call_date: string;
  next_followup_date?: string | null;
}

export interface FollowUpRow {
  student_id: string;
  profile_id: string;
  name: string;
  prn: string | null;
  phone: string | null;
  batch: string | null;
  installment_id: string;
  installment_number: number;
  due_date: string;
  amount_due: number;
  days_overdue: number;
  last_remark: string | null;
  last_remark_date: string | null;
}

export interface FollowUpDashboard {
  day: string;
  dues: FollowUpRow[];
  commitments: FollowUpRow[];
  overdue: FollowUpRow[];
  dues_total: number;
  commitments_total: number;
  overdue_total: number;
}

export interface ForecastDay {
  date: string;
  installments_due: number;
  expected_amount: number;
}

export interface ForecastRange {
  from_date: string;
  to_date: string;
  days: ForecastDay[];
  total_installments: number;
  total_expected: number;
}

export interface CollectionSummary {
  total_agreed: number;
  total_collected: number;
  total_pending: number;
  collection_pct: number;
  student_count: number;
  batch_id: string | null;
}

export interface StaffPerformanceRow {
  staff_id: string;
  staff_name: string;
  calls_made: number;
  collection: number;
}

export interface StaffPerformance {
  day: string;
  staff: StaffPerformanceRow[];
}

// ₹ formatting (Indian grouping).
export function inr(n: number | null | undefined): string {
  if (n == null) return "—";
  return "₹" + Math.round(n).toLocaleString("en-IN");
}
