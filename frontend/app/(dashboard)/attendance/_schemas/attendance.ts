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
