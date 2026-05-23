// Generated from OpenAPI spec (GET /openapi.json → components.schemas)

export const STANDARDS = ["9", "10", "11", "12", "Dropper"] as const;
export type Standard = (typeof STANDARDS)[number];

export const TARGET_EXAMS = [
  "NEET",
  "JEE-Main",
  "JEE-Advanced",
  "Both",
  "Foundation",
  "Other",
] as const;
export type TargetExam = (typeof TARGET_EXAMS)[number];

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
  gender: string | null;
  district: string | null;
  caste: string | null;
  username: string | null;
  course_id: string | null;
  standard: Standard | null;
  target_exam: TargetExam | null;
  status: string;
}

export interface StudentCreate {
  branch_id: string;
  academic_year_id: string;
  first_name: string;
  last_name: string;
  standard: Standard;
  target_exam: TargetExam;
  email?: string | null;
  phone?: string | null;
  date_of_birth?: string | null;
  enrollment_number?: string | null;
  parent_mobile?: string | null;
  rfid_number?: string | null;
  gender?: string | null;
  district?: string | null;
  caste?: string | null;
  username?: string | null;
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
  gender?: string | null;
  district?: string | null;
  caste?: string | null;
  username?: string | null;
  course_id?: string | null;
  standard?: Standard | null;
  target_exam?: TargetExam | null;
}

export interface AcademicYearResponse {
  id: string;
  branch_id: string;
  name: string;
  start_year: number;
  end_year: number;
  status: string;
}
