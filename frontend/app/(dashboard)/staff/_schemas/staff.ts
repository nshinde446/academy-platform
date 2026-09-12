// Mirrors backend Pydantic schemas in app/modules/staff/schemas/staff_schemas.py

export interface DepartmentWithAllocation {
  id: string;
  branch_id: string;
  name: string;
  id_range_start: number;
  id_range_end: number;
  used: number;
  next_emp_code: string | null;
}

export interface StaffResponse {
  id: string;
  branch_id: string;
  emp_code: string;
  title: string | null;
  first_name: string;
  last_name: string;
  department_id: string;
  department_name: string | null;
  designation: string | null;
  linked_teacher_id: string | null;
  email: string | null;
  phone: string | null;
  is_legacy_code: boolean;
  shift_start: string | null;
  shift_end: string | null;
  weekly_off_days: string | null;
  status: string;
}

export interface StaffCreate {
  branch_id: string;
  first_name: string;
  last_name?: string;
  title?: string | null;
  department_id: string;
  designation?: string | null;
  linked_teacher_id?: string | null;
  email?: string | null;
  phone?: string | null;
  emp_code?: string | null;
  shift_start?: string | null;
  shift_end?: string | null;
  weekly_off_days?: string | null;
}

export interface StaffUpdate {
  first_name?: string | null;
  last_name?: string | null;
  title?: string | null;
  department_id?: string | null;
  designation?: string | null;
  linked_teacher_id?: string | null;
  email?: string | null;
  phone?: string | null;
  emp_code?: string | null;
  shift_start?: string | null;
  shift_end?: string | null;
  weekly_off_days?: string | null;
}

export interface ImportSummary {
  imported: number;
  skipped: number;
  errors: string[];
}
