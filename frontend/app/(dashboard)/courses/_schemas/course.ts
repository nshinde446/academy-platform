// Generated from OpenAPI spec (GET /openapi.json → components.schemas)

export interface CourseResponse {
  id: string;
  branch_id: string;
  academic_year_id: string;
  name: string;
  code: string;
  description: string | null;
  status: string;
}

export interface CourseCreate {
  branch_id: string;
  academic_year_id: string;
  name: string;
  code: string;
  description?: string | null;
}

export interface AcademicYearResponse {
  id: string;
  branch_id: string;
  name: string;
  start_year: number;
  end_year: number;
  status: string;
}
