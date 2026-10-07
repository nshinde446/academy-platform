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
  // Manual-entry audit trail (PDF3). entry_type: "BIOMETRIC" | "MANUAL" | null
  // (no entry yet). marked_by is "Name (Role)" for a manual entry, else null.
  entry_type: string | null;
  marked_by: string | null;
  marked_at: string | null;
}

// Manager hand-enters a staff In Time (and optionally Out Time) when the device
// missed the punch. Times are "HH:MM" (24h), branch-local.
export interface StaffManualMarkRequest {
  staff_id: string;
  day: string;
  in_time: string;
  out_time: string | null;
}
