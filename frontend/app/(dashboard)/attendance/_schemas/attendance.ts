// Attendance domain shapes. Kept in sync with the backend Pydantic
// schemas in app/modules/attendance/schemas/attendance_schemas.py and the
// service-level enums in attendance_service.py.

export const ATTENDANCE_STATUSES = [
  "PRESENT",
  "ABSENT",
  "LATE",
  "PARTIAL",
  "EXCUSED",
  "MANUAL_OVERRIDE",
] as const;
export type AttendanceStatus = (typeof ATTENDANCE_STATUSES)[number];

export type AttendanceSource = "BIOMETRIC" | "MANUAL" | "IMPORT" | "SYSTEM";

export interface AttendanceRecord {
  id: string;
  student_id: string;
  lecture_id: string;
  attendance_status: AttendanceStatus;
  marked_at: string;
  marked_by: string | null;
  source: AttendanceSource;
  branch_id: string;
  status: string;
}

export interface AttendanceMarkRequest {
  student_id: string;
  attendance_status: AttendanceStatus;
  // Defaults to MANUAL on the backend; we always send it explicitly so the
  // record's provenance is clear in the audit log.
  source?: AttendanceSource;
}

// Minimal roster row the marking table needs — built from
// GET /students/with-stats filtered to the lecture's batch.
export interface RosterStudent {
  id: string;
  first_name: string;
  last_name: string;
  enrollment_number: string | null;
}

// ── Day-attendance (Layer 1) — population campus presence ───────────────────
// Mirrors the backend DailyAttendance reports. A "day" row is one student on
// one local day, independent of any lecture.

export type DayStatus = "PRESENT" | "LATE" | "ABSENT";
export type Signoff = "COMPLETE" | "MISSING" | "NA";

// One line in a classroom day register (Reference B export — P/A roster).
export interface ClassroomRegisterRow {
  student_id: string;
  name: string;
  enrollment_number: string | null;
  parent_mobile: string | null;
  mark: "P" | "A";
  day_status: DayStatus;
  first_in: string | null;
  last_out: string | null;
  signoff: Signoff;
}

// One day in a student's timeline (Reference A export — IN/OUT/status by day).
export interface DailyAttendance {
  id: string;
  student_id: string;
  branch_id: string;
  attendance_date: string;
  first_in: string | null;
  last_out: string | null;
  day_status: DayStatus;
  signoff: Signoff;
  source: AttendanceSource;
}

export interface AttendanceSummary {
  student_id: string;
  working_days: number;
  present_days: number;
  absent_days: number;
  attendance_pct: number;
}

// One student below the attendance threshold over a range, aggregated across
// their batches. Mirrors the backend DefaulterRow (daily/defaulters).
export interface DefaulterRow {
  student_id: string;
  name: string;
  enrollment_number: string | null;
  batches: string[];
  present: number;
  working_days: number;
  attendance_pct: number;
}
