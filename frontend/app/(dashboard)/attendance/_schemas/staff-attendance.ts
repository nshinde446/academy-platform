// Staff day-register row — one staff member's attendance for a single day,
// mirroring the student ClassroomRegisterRow but for the staff biometric path.
export interface StaffDayRegisterRow {
  staff_id: string;
  emp_code: string;
  name: string;
  department: string;
  in_time: string | null;
  out_time: string | null;
  work_minutes: number;
  ot_minutes: number;
  status: string;
  missed_signoff: boolean;
}
