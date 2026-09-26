// Teacher Productivity Report (client document) — the cumulative summary table
// (Section 3) + the two pie-chart aggregates (Section 5), over a date range
// (Section 4). Replaces the earlier lecture-centric dashboard schema.

export interface ProductivitySummaryRow {
  emp_code: string;
  initials: string;
  teacher_name: string;
  subject: string;
  present_days: number;
  total_lectures: number;
  scheduled_minutes: number;
  delivered_minutes: number;
}

export interface ProductivityChartSlice {
  label: string;
  lectures: number;
}

export interface ProductivitySummaryResponse {
  start: string;
  end: string;
  rows: ProductivitySummaryRow[];
  by_subject: ProductivityChartSlice[];
  by_teacher: ProductivityChartSlice[];
}

export interface ProductivityFilters {
  fromDate: string;
  toDate: string;
  teacherIds: string[];
}
