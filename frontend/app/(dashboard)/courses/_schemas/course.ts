// Generated from OpenAPI spec (GET /openapi.json → components.schemas)

export interface CourseResponse {
  id: string;
  branch_id: string;
  name: string;
  code: string;
  description: string | null;
  duration_years: number;
  status: string;
}

export interface CourseCreate {
  branch_id: string;
  name: string;
  code: string;
  description?: string | null;
  duration_years?: number;
}

export interface CourseUpdate {
  name?: string;
  code?: string;
  description?: string | null;
  duration_years?: number;
}
