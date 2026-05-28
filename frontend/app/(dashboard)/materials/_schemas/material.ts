// Mirror of backend/app/modules/materials/schemas/material_schemas.py.
// Keep these in sync when the backend schema changes.

export const MATERIAL_CATEGORIES = [
  "ncert",
  "dpp",
  "cpp",
  "topic_wise",
  "pyq",
  "notes",
  "other",
] as const;
export type MaterialCategory = (typeof MATERIAL_CATEGORIES)[number];

export const CATEGORY_LABEL: Record<MaterialCategory, string> = {
  ncert: "NCERT",
  dpp: "DPP",
  cpp: "CPP",
  topic_wise: "Topic-wise",
  pyq: "PYQ",
  notes: "Notes",
  other: "Other",
};

export const EXAM_TYPES = [
  "neet",
  "jee_main",
  "jee_advanced",
  "boards",
  "cet",
  "other",
] as const;
export type ExamType = (typeof EXAM_TYPES)[number];

export const EXAM_TYPE_LABEL: Record<ExamType, string> = {
  neet: "NEET",
  jee_main: "JEE Main",
  jee_advanced: "JEE Adv",
  boards: "Boards",
  cet: "CET",
  other: "Other",
};

export const INGEST_STATUSES = [
  "uploaded",
  "ingesting",
  "ingested",
  "ingest_failed",
  "archived",
] as const;
export type IngestStatus = (typeof INGEST_STATUSES)[number];

export const CLASS_LABELS = ["9", "10", "11", "12", "drop"] as const;
export type ClassLabel = (typeof CLASS_LABELS)[number];

export interface MaterialResponse {
  id: string;
  filename: string;
  storage_key: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  academic_year_id: string;
  class_label: string;
  subject_id: string;
  topic: string | null;
  category: MaterialCategory;
  exam_types: string[];
  description: string | null;
  ingest_status: IngestStatus;
  ingest_error: string | null;
  ingest_pages_total: number | null;
  ingest_pages_done: number | null;
  question_count: number;
  branch_id: string;
  created_at: string;
  updated_at: string;
  created_by: string | null;
}

export interface MaterialListResponse {
  items: MaterialResponse[];
  total: number;
}

export interface FacetBucket {
  value: string;
  count: number;
}

export interface MaterialFacetCounts {
  classes: FacetBucket[];
  subjects: FacetBucket[];
  categories: FacetBucket[];
  exam_types: FacetBucket[];
  batches: FacetBucket[];
}

export interface MaterialUploadFields {
  academic_year_id: string;
  class_label: string;
  subject_id: string;
  category: MaterialCategory;
  exam_types: ExamType[];
  topic?: string;
  description?: string;
  batch_ids?: string[];
}
