// Generated from OpenAPI spec (GET /openapi.json → components.schemas)

export interface SubjectResponse {
  id: string;
  branch_id: string;
  academic_year_id: string;
  course_id: string;
  name: string;
  code: string;
  status: string;
}

export interface SubjectCreate {
  branch_id: string;
  academic_year_id: string;
  course_id: string;
  name: string;
  code: string;
}

export interface SubjectSeedRequest {
  branch_id: string;
  course_id: string;
  syllabus_key: string;
}

export interface SubjectSeedResponse {
  created: number;
  subjects: SubjectResponse[];
}

export interface SyllabusOption {
  key: string;
  label: string;
  subjects: string[];
}
