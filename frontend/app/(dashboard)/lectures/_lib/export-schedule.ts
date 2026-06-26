// Download the current (filtered) lecture schedule as a CSV the admin can
// keep, print, or hand off. The lectures list is already fully loaded on the
// page (unlike the server-paged student roster), so we just project the rows
// in hand through the same name lookups the table uses and reuse the shared
// CSV helper.

import { downloadCsvTemplate } from "@/lib/csv-template";
import type {
  BatchSummary,
  ClassroomSummary,
  LectureResponse,
  SubjectSummary,
  TeacherSummary,
  TopicSummary,
} from "../_schemas/lecture";

export interface ScheduleLookups {
  batches: BatchSummary[];
  teachers: TeacherSummary[];
  subjects: SubjectSummary[];
  topics: TopicSummary[];
  classrooms: ClassroomSummary[];
}

const EXPORT_HEADERS = [
  "Batch",
  "Teacher",
  "Actual teacher",
  "Subject",
  "Topic",
  "Classroom",
  "Delivery",
  "Scheduled start",
  "Scheduled end",
  "Actual start",
  "Actual end",
  "Duration (min)",
  "Status",
  "Late start",
  "No-show reason",
  "Notes",
];

function fmt(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  // Local, sortable, Excel-friendly: "2026-06-26 16:00".
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

function nameOf<T extends { id: string }>(
  list: T[],
  id: string | null,
  render: (x: T) => string,
): string {
  if (!id) return "";
  const found = list.find((x) => x.id === id);
  return found ? render(found) : "";
}

export function scheduleToRows(
  lectures: LectureResponse[],
  lk: ScheduleLookups,
): string[][] {
  const teacherName = (id: string | null) =>
    nameOf(lk.teachers, id, (t) =>
      `${t.first_name} ${t.last_name}`.trim(),
    );
  return lectures.map((l) => [
    nameOf(lk.batches, l.batch_id, (b) => b.name),
    teacherName(l.teacher_id),
    teacherName(l.actual_teacher_id),
    nameOf(lk.subjects, l.subject_id, (s) => s.name),
    nameOf(lk.topics, l.topic_id, (t) => t.name),
    nameOf(lk.classrooms, l.classroom_id, (c) => c.name),
    l.delivery_mode,
    fmt(l.scheduled_start),
    fmt(l.scheduled_end),
    fmt(l.actual_start),
    fmt(l.actual_end),
    l.actual_duration_min != null ? String(l.actual_duration_min) : "",
    l.lecture_status,
    l.late_flag === true ? "yes" : "",
    l.no_show_reason ?? "",
    l.notes ?? "",
  ]);
}

/** Trigger a CSV download of the given (already-filtered) lectures. */
export function downloadScheduleCsv(
  lectures: LectureResponse[],
  lk: ScheduleLookups,
): void {
  const stamp = new Date().toISOString().slice(0, 10);
  downloadCsvTemplate(
    `schedule-${stamp}.csv`,
    EXPORT_HEADERS,
    scheduleToRows(lectures, lk),
  );
}
