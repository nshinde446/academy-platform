// Generated from OpenAPI spec (GET /openapi.json → components.schemas)

export interface StudentResponse {
  id: string;
  branch_id: string;
  academic_year_id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  date_of_birth: string | null;
  enrollment_number: string | null;
  parent_mobile: string | null;
  rfid_number: string | null;
  course_id: string | null;
  status: string;
}

export interface StudentCreate {
  branch_id: string;
  academic_year_id: string;
  first_name: string;
  last_name: string;
  email?: string | null;
  phone?: string | null;
  date_of_birth?: string | null;
  enrollment_number?: string | null;
  parent_mobile?: string | null;
  rfid_number?: string | null;
  course_id?: string | null;
}

export interface StudentUpdate {
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
  date_of_birth?: string | null;
  enrollment_number?: string | null;
  parent_mobile?: string | null;
  rfid_number?: string | null;
  course_id?: string | null;
}

export interface AcademicYearResponse {
  id: string;
  branch_id: string;
  name: string;
  start_year: number;
  end_year: number;
  status: string;
}
