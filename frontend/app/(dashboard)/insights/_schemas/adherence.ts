export interface AdherenceTotals {
  planned: number;
  completed_as_planned: number;
  substituted: number;
  cancelled: number;
  no_show: number;
  rescheduled: number;
}

export interface AdherenceSessions {
  planned: number;
  makeup: number;
  ad_hoc: number;
  merged: number;
}

export interface AdherenceRates {
  adherence_pct: number;
  substitute_pct: number;
  cancellation_pct: number;
  no_show_pct: number;
  teacher_no_show_pct: number;
}

export interface AdherenceNoShowBreakdown {
  teacher: number;
  student: number;
  external: number;
  other: number;
}

export interface SyllabusBatchRow {
  batch_id: string;
  batch_name: string;
  batch_code: string;
  course_id: string;
  total_topics: number;
  delivered_topics: number;
  coverage_pct: number;
}

export interface AdherenceTeacherRow {
  teacher_id: string;
  first_name: string;
  last_name: string;
  planned: number;
  substituted_out: number;
  substituted_in: number;
  cancelled: number;
  substitute_rate_pct: number;
}

export interface AdherenceResponse {
  from_date: string | null;
  to_date: string | null;
  totals: AdherenceTotals;
  sessions: AdherenceSessions;
  rates: AdherenceRates;
  no_show_breakdown: AdherenceNoShowBreakdown;
  by_teacher: AdherenceTeacherRow[];
  by_batch_syllabus: SyllabusBatchRow[];
}
