// Test Portal (Phase 1) shapes — mirror the backend tests module schemas.

export interface TestSummary {
  id: string;
  name: string;
  batch_id: string;
  subject_id: string;
  subject_ids: string[];
  scheduled_at: string | null;
  total_marks: number;
  omr_type: string | null;
  test_status: string;
}

export interface ScheduleTestInput {
  name: string;
  batch_id: string;
  subject_ids: string[];
  scheduled_at: string | null;
  total_marks: number;
  omr_type: string | null;
}

export interface UploadResultSummary {
  matched: number;
  needs_review: number;
  absent: number;
  total_rows: number;
}

export interface RankRow {
  rank: number | null;
  student_id: string;
  prn: string | null;
  name: string;
  marks_obtained: number | null;
  percentage: number | null;
  absent: boolean;
}

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
  ranked: RankRow[];
  absentees: RankRow[];
  needs_review: ReviewRow[];
}

// OMR layouts the academy prints (ZipGrade sheet types).
export const OMR_TYPES = ["50Q", "100Q", "200Q"] as const;
