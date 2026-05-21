// Mirrors backend Pydantic schemas in app/modules/teacher/schemas/teacher_schemas.py

export interface TeacherResponse {
  id: string;
  branch_id: string;
  user_id: string | null;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  qualification: string | null;
  status: string;
}

export interface TeacherCreate {
  branch_id: string;
  first_name: string;
  last_name: string;
  email?: string | null;
  phone?: string | null;
  qualification?: string | null;
}

export interface TeacherUpdate {
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
  qualification?: string | null;
}

export interface ImportSummary {
  imported: number;
  skipped: number;
  errors: string[];
}
