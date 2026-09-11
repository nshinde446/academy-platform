// Generated from OpenAPI spec (GET /openapi.json → components.schemas)

export interface BatchResponse {
  id: string;
  branch_id: string;
  start_academic_year_id: string;
  end_academic_year_id: string;
  course_id: string;
  name: string;
  code: string;
  capacity: number;
  duration_years: number;
  target_exam_date: string | null;
  // Class window "HH:MM" (24h). class_start_time is the Present/Late cutoff;
  // null falls back to the institute default.
  class_start_time: string | null;
  class_end_time: string | null;
  status: string;
}

export interface BatchCreate {
  branch_id: string;
  start_academic_year_id: string;
  course_id: string;
  name: string;
  code: string;
  capacity?: number;
  target_exam_date?: string | null;
  class_start_time?: string | null;
  class_end_time?: string | null;
}

export interface BatchUpdate {
  name?: string | null;
  code?: string | null;
  capacity?: number | null;
  target_exam_date?: string | null;
  class_start_time?: string | null;
  class_end_time?: string | null;
}

export interface CourseResponse {
  id: string;
  branch_id: string;
  name: string;
  code: string;
  description: string | null;
  duration_years: number;
  status: string;
}

export interface AcademicYearResponse {
  id: string;
  branch_id: string;
  name: string;
  start_year: number;
  end_year: number;
  status: string;
}
