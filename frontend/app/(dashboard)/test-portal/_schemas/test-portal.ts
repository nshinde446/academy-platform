// Test Portal (Phase 1) shapes — mirror the backend tests module schemas.

export interface TestSummary {
  id: string;
  name: string;
  paper_type: string;
  batch_id: string;
  batch_ids: string[];
  subject_id: string;
  subject_ids: string[];
  scheduled_at: string | null;
  total_marks: number;
  question_type: string;
  omr_type: string | null;
  answer_key_file: string | null;
  test_status: string;
}

// A subject on a test plus its per-subject total marks (per-subject flow).
export interface SubjectInput {
  subject_id: string;
  total_marks: number;
}

export interface ScheduleTestInput {
  name: string;
  // OMR flow: single batch_id + subject_ids. Per-subject flow: batch_ids[] +
  // subjects[{subject_id,total_marks}] + question_type.
  batch_id?: string;
  batch_ids?: string[];
  subject_ids?: string[];
  subjects?: SubjectInput[];
  scheduled_at: string | null;
  total_marks: number;
  question_type?: string;
  omr_type?: string | null;
}

export interface UploadResultSummary {
  matched: number;
  needs_review: number;
  absent: number;
  total_rows: number;
}

export interface SubjectUploadSummary {
  subject_id: string;
  matched: number;
  unmatched: number;
  absent: number;
  errors: string[];
  all_subjects_uploaded: boolean;
}

export interface RankRow {
  rank: number | null;
  student_id: string;
  prn: string | null;
  name: string;
  marks_obtained: number | null;
  percentage: number | null;
  absent: boolean;
  // Per-subject marks keyed by subject name (null = absent for that subject).
  subject_marks: Record<string, number | null>;
}

export interface SubjectColumn {
  subject_id: string;
  subject_name: string;
  total_marks: number | null;
}

// JEE question styles. NA for CET/NEET (and all OMR tests).
export const QUESTION_TYPES = [
  { value: "MCQ_ONLY", label: "MCQ only" },
  { value: "MCQ_NUMERICAL", label: "MCQ + Numerical" },
] as const;

export interface ReviewRow {
  id: string;
  csv_prn: string | null;
  csv_name: string | null;
  resolved: boolean;
}

export interface RankList {
  test_id: string;
  test_name: string;
  total_marks: number;
  subjects: SubjectColumn[];
  ranked: RankRow[];
  absentees: RankRow[];
  needs_review: ReviewRow[];
}

// OMR layouts the academy prints (ZipGrade sheet types).
export const OMR_TYPES = ["50Q", "100Q", "200Q"] as const;
