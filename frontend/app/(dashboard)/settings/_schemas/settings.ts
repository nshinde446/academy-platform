export type DigestScope = "ALL" | "ABSENT_ONLY";

export interface NotificationSettings {
  branch_id: string;
  daily_digest_enabled: boolean;
  daily_digest_scope: DigestScope;
  // Per-branch master switch for all WhatsApp sends (UI on/off).
  whatsapp_enabled: boolean;
}

export interface NotificationSettingsUpdate {
  daily_digest_enabled?: boolean;
  daily_digest_scope?: DigestScope;
  whatsapp_enabled?: boolean;
}

// An editable message template (mirrors the backend NotificationTemplate).
export interface NotificationTemplate {
  id: string;
  name: string;
  event_type: string;
  channel: string;
  subject: string | null;
  body_template: string;
  is_active: boolean;
  branch_id: string | null;
  provider_template_name: string | null;
  provider_language: string | null;
}

export interface NotificationTemplateUpdate {
  body_template?: string;
  is_active?: boolean;
  provider_template_name?: string | null;
  provider_language?: string | null;
}

// Human labels for the event types the editor groups templates by.
export const EVENT_TYPE_LABELS: Record<string, string> = {
  STUDENT_ABSENT: "Attendance — absent alert",
  DAILY_ATTENDANCE_DIGEST: "Attendance — daily digest",
  LECTURE_REMINDER: "Lecture reminder",
  ATTENDANCE_MARKED: "Attendance marked",
  TEST_UPLOADED: "Test uploaded",
  MARKS_UPDATED: "Marks updated",
  LECTURE_COMPLETED: "Lecture completed",
  LECTURE_CANCELLED: "Lecture cancelled",
};
