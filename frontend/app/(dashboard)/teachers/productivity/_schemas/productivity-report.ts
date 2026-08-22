// Mirrors backend Pydantic schemas in
// app/modules/lectures/schemas/lecture_schemas.py (Productivity report).

export interface ProductivityReportTeacherRow {
  teacher_id: string;
  first_name: string;
  last_name: string;
  scheduled: number;
  conducted: number;
  completion_pct: number | null;
  hours: number;
  minutes: number;
  on_time_count: number;
  late_count: number;
  punctuality_pct: number | null;
  avg_delay_min: number;
  topics_planned: number;
  topics_covered: number;
}

export interface ProductivityReportSubjectRow {
  subject_id: string;
  subject_name: string;
  scheduled: number;
  conducted: number;
  completion_pct: number | null;
  hours: number;
  minutes: number;
}

export interface ProductivityReportBatchRow {
  batch_id: string;
  batch_name: string;
  scheduled: number;
  conducted: number;
  completion_pct: number | null;
  hours: number;
  minutes: number;
}

export interface ProductivityReportTrendPoint {
  iso_year: number;
  iso_week: number;
  label: string;
  scheduled: number;
  conducted: number;
  completion_pct: number | null;
  punctuality_pct: number | null;
  hours: number;
}

export interface ProductivityReportSummary {
  teachers: number;
  total_scheduled: number;
  total_conducted: number;
  total_hours: number;
  completion_pct: number | null;
  punctuality_pct: number | null;
}

export interface ProductivityReportResponse {
  from_date: string | null;
  to_date: string | null;
  summary: ProductivityReportSummary;
  by_teacher: ProductivityReportTeacherRow[];
  by_subject: ProductivityReportSubjectRow[];
  by_batch: ProductivityReportBatchRow[];
  trend: ProductivityReportTrendPoint[];
}

export interface ProductivityReportFilters {
  fromDate: string;
  toDate: string;
  batchIds: string[];
  subjectIds: string[];
  teacherIds: string[];
}
