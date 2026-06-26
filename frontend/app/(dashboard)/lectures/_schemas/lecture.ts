// Lecture domain shapes. Re-defined locally to keep the page self-contained;
// kept in sync with backend Pydantic schemas.

export type LectureStatus =
  | "scheduled"
  | "started"
  | "paused"
  | "completed"
  | "cancelled"
  | "no_show"
  | "rescheduled";

export type NoShowReason =
  | "TEACHER_NO_SHOW"
  | "STUDENT_NO_SHOW"
  | "EXTERNAL"
  | "OTHER";

export type ChangeReason =
  | "SUBSTITUTE"
  | "SUBJECT_SWAP"
  | "TOPIC_CHANGE"
  | "COMBINED_BATCH"
  | "OTHER";

export interface LectureResponse {
  id: string;
  teacher_id: string;
  batch_id: string;
  classroom_id: string | null;
  subject_id: string;
  topic_id: string | null;
  scheduled_start: string;
  scheduled_end: string;
  actual_start: string | null;
  actual_end: string | null;
  late_flag: boolean | null;
  actual_duration_min: number | null;
  delivery_mode: string;
  lecture_status: LectureStatus;
  notes: string | null;
  actual_teacher_id: string | null;
  change_reason: ChangeReason | null;
  change_notes: string | null;
  no_show_reason: NoShowReason | null;
  branch_id: string;
  academic_year_id: string;
  status: string;
}

export interface LectureSubstitute {
  actual_teacher_id: string | null;
  change_reason?: ChangeReason | null;
  change_notes?: string | null;
}

export interface LectureNoShow {
  no_show_reason: NoShowReason;
  notes?: string | null;
}

export interface LectureActuals {
  actual_start?: string | null;
  actual_end?: string | null;
  topic_id?: string | null;
  notes?: string | null;
}

export interface CopyScheduleSummary {
  source_date: string;
  target_date: string;
  copied: number;
  skipped: number;
  errors: string[];
}

// S3 — recurring weekly timetable. day_of_week: Mon=0 … Sun=6.
export interface TimetableSlot {
  day_of_week: number;
  start_time: string; // HH:MM
  end_time: string; // HH:MM
  subject_id: string | null;
  teacher_id: string | null;
  classroom_id: string | null;
  delivery_mode: string;
}

export interface TimetableSlotResponse extends TimetableSlot {
  id: string;
  batch_id: string;
}

export interface GenerateScheduleSummary {
  from_date: string;
  to_date: string;
  generated: number;
  skipped: number;
  errors: string[];
}

// S4 — holiday calendar (non-teaching days the scheduler skips).
export interface HolidayResponse {
  id: string;
  branch_id: string;
  holiday_date: string; // YYYY-MM-DD
  name: string;
}

// S5 — a teacher who can actually cover a lecture (qualified, free, not on leave).
export interface EligibleSubstitute {
  teacher_id: string;
  first_name: string;
  last_name: string;
}

// S5 — a teacher's planned unavailability (inclusive date range).
export interface TeacherLeaveResponse {
  id: string;
  teacher_id: string;
  branch_id: string;
  start_date: string; // YYYY-MM-DD
  end_date: string; // YYYY-MM-DD
  reason: string | null;
}

export interface ProductivityTeacherRow {
  teacher_id: string;
  first_name: string;
  last_name: string;
  lectures_taught: number;
  hours_taught: number;
  avg_lecture_min: number;
  late_count: number;
  on_time_count: number;
  punctuality_pct: number;
  distinct_topics: number;
}

export interface ProductivitySummary {
  teachers: number;
  total_lectures: number;
  total_hours: number;
  total_late: number;
  branch_punctuality_pct: number;
}

export interface ProductivityResponse {
  from_date: string | null;
  to_date: string | null;
  summary: ProductivitySummary;
  by_teacher: ProductivityTeacherRow[];
}

export interface LectureCreate {
  teacher_id: string;
  batch_id: string;
  classroom_id?: string | null;
  subject_id: string;
  topic_id?: string | null;
  scheduled_start: string;
  scheduled_end: string;
  delivery_mode?: string;
  notes?: string | null;
}

export type SessionOrigin = "planned" | "makeup" | "ad_hoc";
export type SessionStatus = "in_progress" | "completed" | "aborted";

export interface LectureSessionCreate {
  teacher_id: string;
  subject_id: string;
  batch_ids: string[];
  lecture_ids?: string[];
  classroom_id?: string | null;
  topic_id?: string | null;
  actual_start: string;
  actual_end?: string | null;
  delivery_mode?: string;
  origin?: SessionOrigin;
  notes?: string | null;
}

export interface LectureSessionResponse {
  id: string;
  teacher_id: string;
  subject_id: string;
  topic_id: string | null;
  classroom_id: string | null;
  actual_start: string;
  actual_end: string | null;
  delivery_mode: string;
  session_status: SessionStatus;
  origin: SessionOrigin;
  notes: string | null;
  branch_id: string;
  academic_year_id: string;
  batch_ids: string[];
  lecture_ids: string[];
  status: string;
}

// Minimal related-entity shapes used by this page.

export interface BatchSummary {
  id: string;
  name: string;
  code: string;
  course_id: string;
}

export interface TeacherSummary {
  id: string;
  first_name: string;
  last_name: string;
}

export interface SubjectSummary {
  id: string;
  name: string;
  code: string;
  course_id: string;
}

export interface TopicSummary {
  id: string;
  name: string;
  chapter_id: string;
}

export interface ClassroomSummary {
  id: string;
  name: string;
  code: string;
  capacity: number;
}
