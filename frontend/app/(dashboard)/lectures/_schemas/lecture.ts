// Lecture domain shapes. Re-defined locally to keep the page self-contained;
// kept in sync with backend Pydantic schemas.

export type LectureStatus =
  | "scheduled"
  | "started"
  | "paused"
  | "completed"
  | "cancelled"
  | "rescheduled";

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
  delivery_mode: string;
  lecture_status: LectureStatus;
  notes: string | null;
  actual_teacher_id: string | null;
  change_reason: ChangeReason | null;
  change_notes: string | null;
  branch_id: string;
  academic_year_id: string;
  status: string;
}

export interface LectureSubstitute {
  actual_teacher_id: string | null;
  change_reason?: ChangeReason | null;
  change_notes?: string | null;
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
