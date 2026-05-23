export type StatusTone = "default" | "secondary" | "success" | "destructive";

export interface RosterSnapshot {
  planned: number;
  completed: number;
  in_progress: number;
  pending: number;
  no_show_teacher: number;
  no_show_other: number;
  cancelled: number;
  off_plan_makeup: number;
  off_plan_ad_hoc: number;
  off_plan_merged: number;
}

export interface RosterEvent {
  kind: "lecture" | "session";
  id: string;
  start: string;
  end: string | null;
  status_label: string;
  status_tone: StatusTone;
  status_sub: string | null;
  batch_name: string | null;
  batch_names: string[];
  subject_name: string | null;
  topic_name: string | null;
  classroom_name: string | null;
  actual_teacher_id: string | null;
  actual_teacher_name: string | null;
  no_show_reason: string | null;
  is_covered: boolean;
  origin: string | null;
}

export interface RosterLiveNow {
  kind: "live" | "overdue";
  lecture_id: string;
  teacher_id: string;
  teacher_name: string;
  batch_name: string | null;
  subject_name: string | null;
  topic_name: string | null;
  classroom_name: string | null;
  scheduled_start: string;
  scheduled_end: string;
  minutes_overdue?: number | null;
}

export interface RosterTeacherSummary {
  planned: number;
  completed: number;
  in_progress: number;
  no_show: number;
  cancelled: number;
  sub_in: number;
  sub_out: number;
  off_plan: number;
}

export interface RosterTeacherRow {
  teacher_id: string;
  first_name: string;
  last_name: string;
  summary: RosterTeacherSummary;
  events: RosterEvent[];
}

export interface RosterIdleTeacher {
  teacher_id: string;
  first_name: string;
  last_name: string;
}

export interface RosterResponse {
  date: string;
  now: string;
  snapshot: RosterSnapshot;
  live_now: RosterLiveNow[];
  teachers: RosterTeacherRow[];
  idle_teachers: RosterIdleTeacher[];
}
