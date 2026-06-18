// Generated from OpenAPI spec (GET /openapi.json → components.schemas)

export const STANDARDS = ["9", "10", "11", "12", "Dropper"] as const;
export type Standard = (typeof STANDARDS)[number];

export const TARGET_EXAMS = [
  "NEET",
  "JEE-Main",
  "JEE-Advanced",
  "MHT-CET",
  "Both",
  "Foundation",
  "Other",
] as const;
export type TargetExam = (typeof TARGET_EXAMS)[number];

export type FeesStatus = "paid" | "due" | "overdue" | "partial";

export interface StudentResponse {
  id: string;
  branch_id: string;
  academic_year_id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  date_of_birth: string | null;
  enrollment_number: string | null;
  parent_mobile: string | null;
  rfid_number: string | null;
  gender: string | null;
  district: string | null;
  caste: string | null;
  username: string | null;
  course_id: string | null;
  standard: Standard | null;
  target_exam: TargetExam | null;
  fees_status: FeesStatus | null;
  status: string;
}

// Computed-stats row from GET /students/with-stats. Powers the
// MSA_Design roster table — only the columns the table needs.
export interface StudentWithStats {
  id: string;
  first_name: string;
  last_name: string;
  enrollment_number: string | null;
  standard: Standard | null;
  target_exam: TargetExam | null;
  batch_id: string | null;
  batch_name: string | null;
  fees_status: FeesStatus | null;
  avg_score_pct: number;
  attendance_pct: number;
  dpp_completion_pct: number;
  batch_rank: number | null;
  batch_size: number;
  tests_taken: number;
}

export interface StudentCreate {
  branch_id: string;
  academic_year_id: string;
  first_name: string;
  last_name: string;
  standard: Standard;
  target_exam: TargetExam;
  email?: string | null;
  phone?: string | null;
  date_of_birth?: string | null;
  enrollment_number?: string | null;
  parent_mobile?: string | null;
  rfid_number?: string | null;
  gender?: string | null;
  district?: string | null;
  caste?: string | null;
  username?: string | null;
  course_id?: string | null;
  fees_status?: FeesStatus | null;
}

export interface StudentUpdate {
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
  date_of_birth?: string | null;
  enrollment_number?: string | null;
  parent_mobile?: string | null;
  rfid_number?: string | null;
  gender?: string | null;
  district?: string | null;
  caste?: string | null;
  username?: string | null;
  course_id?: string | null;
  standard?: Standard | null;
  target_exam?: TargetExam | null;
  fees_status?: FeesStatus | null;
}

// A scheduled, not-yet-taken test for the student's batch (soonest first).
export interface StudentUpcomingTest {
  test_id: string;
  test_name: string;
  paper_type: string;
  subject_name: string;
  scheduled_at: string | null;
}

// Per-topic accuracy for the Tier 13 weakness map (weakest first).
export interface StudentTopicMastery {
  topic_id: string;
  topic_name: string;
  subject_name: string;
  attempted: number;
  correct: number;
  accuracy_pct: number;
}

// One row per test the student has taken — powers /students/[id].
export interface StudentTestHistoryRow {
  test_id: string;
  test_name: string;
  paper_type: string;
  scheduled_at: string | null;
  subject_id: string;
  subject_name: string;
  topics: string[];
  marks_obtained: number;
  max_marks: number;
  percentage: number;
  grade: string | null;
  is_absent: boolean;
  batch_rank: number | null;
  batch_size: number;
  institute_rank: number | null;
  institute_size: number;
}

export interface ImportSummary {
  imported: number;
  skipped: number;
  errors: string[];
  // Non-blocking §3 advisories for rows that were still imported.
  warnings: string[];
  batches_created: string[];
  // Subject skeleton rows auto-created for new courses (§8).
  subjects_created: number;
  // Handle to undo this import as a unit. Null when nothing persisted.
  import_id: string | null;
}

export interface ImportUndoSummary {
  students_deleted: number;
  batches_deleted: number;
  subjects_deleted: number;
}

// One distinct Batch code referenced by an upload — whether it already
// exists and, if not, the course/exam-date derived from the Target column.
export interface ImportPreviewBatch {
  code: string;
  student_count: number;
  exists: boolean;
  target: string | null;
  suggested_course_code: string | null;
  suggested_course_name: string | null;
  suggested_exam_date: string | null;
  // Whether auto-create would succeed for a missing code, and why not.
  // Existing batches are always creatable=true, blocker=null.
  creatable: boolean;
  blocker: string | null;
}

// Dry-run of a student upload from POST /students/import/preview.
export interface ImportPreview {
  total_rows: number;
  importable_rows: number;
  rows_missing_name: number;
  rows_invalid_enrolment: number;
  // §3 cross-field contradictions (block) and non-blocking advisories.
  rows_invalid_consistency: number;
  rows_with_warnings: number;
  duplicate_rows: number;
  unbatched_rows: number;
  existing_batches: number;
  missing_batches: number;
  blocked_batches: number;
  // Set when the import can't run at all (e.g. no academic year on the branch).
  blocking_error: string | null;
  batches: ImportPreviewBatch[];
  row_issues: string[];
}

export interface AcademicYearResponse {
  id: string;
  branch_id: string;
  name: string;
  start_year: number;
  end_year: number;
  status: string;
}
