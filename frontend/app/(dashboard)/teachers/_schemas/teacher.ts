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
  years_experience: number | null;
  status: string;
}

export interface TeacherCreate {
  branch_id: string;
  first_name: string;
  last_name: string;
  email?: string | null;
  phone?: string | null;
  qualification?: string | null;
  years_experience?: number | null;
  // Subject names the teacher teaches — drives the Subject→Teacher schedule lock.
  subjects?: string[];
}

export interface TeacherSubjects {
  subjects: string[];
}

export interface TeacherUpdate {
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
  qualification?: string | null;
  years_experience?: number | null;
}

// Computed-stats row from GET /teachers/with-stats. Powers the
// MSA_Design teachers roster (Years, Subject, Lectures (30d), Sub
// rate, Avg outcome).
export interface TeacherWithStats {
  id: string;
  first_name: string;
  last_name: string;
  qualification: string | null;
  years_experience: number | null;
  subject_id: string | null;
  subject_name: string | null;
  lectures_30d: number;
  sub_rate_pct: number;
  avg_outcome_delta_pp: number | null;
}

export interface ImportSummary {
  imported: number;
  skipped: number;
  errors: string[];
}
