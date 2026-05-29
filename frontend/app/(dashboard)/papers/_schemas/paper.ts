// Mirrors backend app/modules/tests/schemas/test_schemas.py (the composer
// builds DPP / CPP / TEST blueprints on the existing tests table — M4).

import type { Difficulty } from "@/app/(dashboard)/question-bank/_schemas/question";

export const PAPER_TYPES = ["DPP", "CPP", "TEST"] as const;
export type PaperType = (typeof PAPER_TYPES)[number];

export const PAPER_TYPE_LABEL: Record<PaperType, string> = {
  DPP: "DPP",
  CPP: "CPP",
  TEST: "Test",
};

export const PAPER_TYPE_HINT: Record<PaperType, string> = {
  DPP: "Daily practice — today's topic",
  CPP: "Class practice — last few topics",
  TEST: "Chapter / full test",
};

export const CLASS_LABELS = ["9", "10", "11", "12", "drop"] as const;
export type ClassLabel = (typeof CLASS_LABELS)[number];

export const EXAM_TYPES = [
  "neet",
  "jee_main",
  "jee_advanced",
  "boards",
  "cet",
] as const;
export type ExamType = (typeof EXAM_TYPES)[number];

export const EXAM_TYPE_LABEL: Record<ExamType, string> = {
  neet: "NEET",
  jee_main: "JEE Main",
  jee_advanced: "JEE Adv",
  boards: "Boards",
  cet: "CET",
};

export const DIFFICULTY_ORDER: Difficulty[] = ["EASY", "MEDIUM", "HARD"];

export type DifficultyMix = Record<Difficulty, number>;

export interface AutoPickRequest {
  subject_id?: string;
  class_label?: string;
  topic?: string;
  exam_type?: string;
  review_status?: string;
  difficulty_mix?: Partial<DifficultyMix>;
  count?: number;
  exclude_ids?: string[];
}

export interface TestResponse {
  id: string;
  name: string;
  description: string | null;
  paper_type: PaperType;
  batch_id: string;
  subject_id: string;
  scheduled_at: string | null;
  duration_minutes: number;
  total_marks: number;
  test_status: string;
  branch_id: string;
  academic_year_id: string;
  status: string;
}
