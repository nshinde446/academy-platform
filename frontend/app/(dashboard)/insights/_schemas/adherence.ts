export interface AdherenceTotals {
  planned: number;
  completed_as_planned: number;
  substituted: number;
  cancelled: number;
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
  by_teacher: AdherenceTeacherRow[];
}
