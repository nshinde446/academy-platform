// Mirrors backend Pydantic schemas in app/modules/tests/schemas/test_schemas.py

export const REVIEW_STATUSES = [
  "pending_review",
  "approved",
  "rejected",
] as const;
export type ReviewStatus = (typeof REVIEW_STATUSES)[number];

export const DIFFICULTIES = ["EASY", "MEDIUM", "HARD"] as const;
export type Difficulty = (typeof DIFFICULTIES)[number];

export const BLOOMS = [
  "REMEMBER",
  "UNDERSTAND",
  "APPLY",
  "ANALYZE",
  "EVALUATE",
  "CREATE",
] as const;
export type Blooms = (typeof BLOOMS)[number];

export interface QuestionResponse {
  id: string;
  content: string;
  options: Record<string, string> | null;
  correct_answer: string;
  explanation: string | null;
  subject_id: string;
  topic_id: string | null;
  difficulty: Difficulty;
  blooms_taxonomy: Blooms;
  concept_tags: string[] | null;
  source: string | null;
  source_ref: string | null;
  diagram_ref: string | null;
  review_status: ReviewStatus;
  quality_score: number | null;
  branch_id: string;
  academic_year_id: string;
  status: string;
}

export interface QuestionUpdate {
  content?: string | null;
  options?: Record<string, string> | null;
  correct_answer?: string | null;
  explanation?: string | null;
  subject_id?: string | null;
  topic_id?: string | null;
  difficulty?: Difficulty | null;
  blooms_taxonomy?: Blooms | null;
  concept_tags?: string[] | null;
  review_status?: ReviewStatus | null;
}

export interface QuestionBulkResult {
  updated: number;
  skipped: string[];
}
