import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CalendarWeekView } from "@/app/(dashboard)/lectures/_components/calendar-week-view";
import type {
  BatchSummary,
  LectureResponse,
  SubjectSummary,
  TeacherSummary,
} from "@/app/(dashboard)/lectures/_schemas/lecture";

const BATCHES: BatchSummary[] = [
  { id: "b1", name: "NEET 2025-A", code: "NEET-A", course_id: "c1" },
];
const TEACHERS: TeacherSummary[] = [
  { id: "t1", first_name: "Asha", last_name: "Kulkarni" },
];
const SUBJECTS: SubjectSummary[] = [
  { id: "s1", name: "Physics", code: "PHY", course_id: "c1" },
];

function makeLecture(over: Partial<LectureResponse> = {}): LectureResponse {
  return {
    id: "l1",
    teacher_id: "t1",
    batch_id: "b1",
    classroom_id: null,
    subject_id: "s1",
    topic_id: null,
    scheduled_start: "2026-06-24T09:00:00Z",
    scheduled_end: "2026-06-24T10:00:00Z",
    actual_start: null,
    actual_end: null,
    late_flag: null,
    actual_duration_min: null,
    delivery_mode: "offline",
    lecture_status: "scheduled",
    notes: null,
    actual_teacher_id: null,
    change_reason: null,
    change_notes: null,
    no_show_reason: null,
    branch_id: "br1",
    academic_year_id: "ay1",
    status: "active",
    ...over,
  };
}

// Mon 2026-06-22 (local), so Wed is 06-24.
const WEEK_START = new Date(2026, 5, 22);

function renderView(lectures: LectureResponse[], handlers = {}) {
  return render(
    <CalendarWeekView
      lectures={lectures}
      batches={BATCHES}
      teachers={TEACHERS}
      subjects={SUBJECTS}
      weekStart={WEEK_START}
      onPrev={vi.fn()}
      onNext={vi.fn()}
      onToday={vi.fn()}
      {...handlers}
    />
  );
}

describe("CalendarWeekView", () => {
  it("renders seven day columns", () => {
    renderView([]);
    expect(screen.getAllByTestId("calendar-day")).toHaveLength(7);
  });

  it("places a lecture in its day with batch + subject", () => {
    // Build the start from a local Wed so bucketing is timezone-stable.
    const l = makeLecture({
      scheduled_start: new Date(2026, 5, 24, 9, 0).toISOString(),
    });
    renderView([l]);
    const card = screen.getByTestId("calendar-lecture");
    expect(card).toHaveTextContent("NEET 2025-A");
    expect(card).toHaveTextContent("Physics");
  });

  it("fires week navigation callbacks", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();
    const onPrev = vi.fn();
    const onToday = vi.fn();
    renderView([], { onNext, onPrev, onToday });
    await user.click(screen.getByRole("button", { name: /next/i }));
    await user.click(screen.getByRole("button", { name: /prev/i }));
    await user.click(screen.getByRole("button", { name: /this week/i }));
    expect(onNext).toHaveBeenCalled();
    expect(onPrev).toHaveBeenCalled();
    expect(onToday).toHaveBeenCalled();
  });
});
