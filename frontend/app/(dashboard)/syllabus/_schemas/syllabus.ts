// Re-defined locally to keep this page self-contained. Mirrors backend
// Pydantic schemas at app/modules/academic/schemas/academic_schemas.py.

export interface SubjectResponse {
  id: string;
  branch_id: string;
  academic_year_id: string;
  course_id: string;
  name: string;
  code: string;
  status: string;
}

export interface ChapterResponse {
  id: string;
  branch_id: string;
  academic_year_id: string;
  subject_id: string;
  name: string;
  order: number;
  status: string;
}

export interface TopicResponse {
  id: string;
  branch_id: string;
  academic_year_id: string;
  chapter_id: string;
  name: string;
  order: number;
  status: string;
}

export interface SubtopicResponse {
  id: string;
  branch_id: string;
  academic_year_id: string;
  topic_id: string;
  name: string;
  order: number;
  status: string;
}

export interface CourseOption {
  id: string;
  name: string;
  code: string;
  duration_years: number;
}

export interface SyllabusImportSummary {
  subjects_created: number;
  chapters_created: number;
  topics_created: number;
  subtopics_created: number;
  rows_processed: number;
  errors: string[];
}

// Composed in-memory tree shape used by the recursive renderer.
export interface TreeTopic {
  id: string;
  name: string;
  subtopics: SubtopicResponse[];
}

export interface TreeChapter {
  id: string;
  name: string;
  topics: TreeTopic[];
}

export interface TreeSubject {
  id: string;
  name: string;
  chapters: TreeChapter[];
}
