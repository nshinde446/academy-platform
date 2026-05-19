// Lecture domain shapes. Re-defined locally to keep the page self-contained;
// kept in sync with backend Pydantic schemas.

export type LectureStatus =
  | "scheduled"
  | "started"
  | "paused"
  | "completed"
  | "cancelled"
  | "rescheduled";

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
  branch_id: string;
  academic_year_id: string;
  status: string;
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
