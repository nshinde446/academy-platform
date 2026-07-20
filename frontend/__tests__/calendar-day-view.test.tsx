import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CalendarDayView } from "@/app/(dashboard)/lectures/_components/calendar-day-view";
import type {
  BatchSummary,
  ClassroomSummary,
  HolidayResponse,
  LectureResponse,
  SubjectSummary,
  TeacherLeaveResponse,
  TeacherSummary,
} from "@/app/(dashboard)/lectures/_schemas/lecture";

const BATCHES: BatchSummary[] = [
  { id: "b1", name: "NEET 2026-A", code: "NEET-A", course_id: "c1" },
  { id: "b2", name: "JEE 2026-B", code: "JEE-B", course_id: "c1" },
];
const TEACHERS: TeacherSummary[] = [
  { id: "t1", first_name: "Asha", last_name: "Kulkarni" },
  { id: "t2", first_name: "Ravi", last_name: "Deshmukh" },
];
const SUBJECTS: SubjectSummary[] = [
  { id: "s1", name: "Physics", code: "PHY", course_id: "c1" },
  { id: "s2", name: "Chemistry", code: "CHE", course_id: "c1" },
];
const CLASSROOMS: ClassroomSummary[] = [
  { id: "r1", name: "Room 201", code: "201", capacity: 60 },
];

// Local midday so nothing straddles a timezone boundary.
const DAY = new Date(2026, 6, 21); // Tue 2026-07-21

function at(h: number, m = 0): string {
  return new Date(2026, 6, 21, h, m).toISOString();
}

function makeLecture(over: Partial<LectureResponse> = {}): LectureResponse {
  return {
    id: "l1",
    teacher_id: "t1",
    batch_id: "b1",
    classroom_id: "r1",
    subject_id: "s1",
    topic_id: null,
    scheduled_start: at(9),
    scheduled_end: at(10),
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

function renderView(
  lectures: LectureResponse[],
  over: {
    holidays?: HolidayResponse[];
    leaves?: TeacherLeaveResponse[];
    onScheduleAt?: (s: Date, e: Date) => void;
    onPrev?: () => void;
    onNext?: () => void;
    onToday?: () => void;
  } = {},
) {
  return render(
    <CalendarDayView
      lectures={lectures}
      batches={BATCHES}
      teachers={TEACHERS}
      subjects={SUBJECTS}
      classrooms={CLASSROOMS}
      holidays={over.holidays ?? []}
      leaves={over.leaves ?? []}
      day={DAY}
      onPrev={over.onPrev ?? vi.fn()}
      onNext={over.onNext ?? vi.fn()}
      onToday={over.onToday ?? vi.fn()}
      onScheduleAt={over.onScheduleAt}
    />,
  );
}

describe("CalendarDayView", () => {
  it("renders the day's lectures with subject, batch, teacher and room", () => {
    renderView([makeLecture()]);
    const row = screen.getByTestId("day-lecture");
    expect(row).toHaveTextContent("Physics");
    expect(row).toHaveTextContent("NEET 2026-A");
    expect(row).toHaveTextContent("Asha Kulkarni");
    expect(row).toHaveTextContent("201");
  });

  it("drops lectures belonging to another day", () => {
    const other = makeLecture({
      id: "l9",
      scheduled_start: new Date(2026, 6, 22, 9).toISOString(),
      scheduled_end: new Date(2026, 6, 22, 10).toISOString(),
    });
    renderView([makeLecture(), other]);
    expect(screen.getAllByTestId("day-lecture")).toHaveLength(1);
  });

  it("offers the gaps around a lecture as free slots", async () => {
    const user = userEvent.setup();
    const onScheduleAt = vi.fn();
    renderView([makeLecture()], { onScheduleAt });
    const slots = screen.getAllByTestId("day-free-slot");
    // 07:00–09:00 before, 10:00–21:00 after.
    expect(slots).toHaveLength(2);
    await user.click(slots[0]);
    const [start, end] = onScheduleAt.mock.calls[0];
    expect(start.getHours()).toBe(7);
    expect(end.getHours()).toBe(9);
  });

  it("frees the slot of a cancelled lecture", () => {
    renderView([makeLecture({ lecture_status: "cancelled" })], {
      onScheduleAt: vi.fn(),
    });
    // Cancelled lecture still shown, but its 09–10 window is not carved out:
    // the whole 07:00–21:00 window stays one free slot.
    expect(screen.getByTestId("day-lecture")).toBeInTheDocument();
    expect(screen.getAllByTestId("day-free-slot")).toHaveLength(1);
  });

  it("flags a teacher double-booked across two batches", () => {
    const a = makeLecture({ id: "a" });
    const b = makeLecture({
      id: "b",
      batch_id: "b2",
      classroom_id: null,
      scheduled_start: at(9, 30),
      scheduled_end: at(10, 30),
    });
    renderView([a, b]);
    expect(screen.getAllByText("Conflict")).toHaveLength(2);
  });

  it("does not flag overlapping lectures that share no resource", () => {
    const a = makeLecture({ id: "a" });
    const b = makeLecture({
      id: "b",
      teacher_id: "t2",
      batch_id: "b2",
      subject_id: "s2",
      classroom_id: null,
      scheduled_start: at(9, 30),
      scheduled_end: at(10, 30),
    });
    renderView([a, b]);
    expect(screen.queryByText("Conflict")).not.toBeInTheDocument();
  });

  it("shows a holiday banner for the day", () => {
    renderView([], {
      holidays: [
        {
          id: "h1",
          branch_id: "br1",
          holiday_date: "2026-07-21",
          name: "Ashadhi Ekadashi",
        },
      ],
    });
    expect(screen.getByTestId("day-holiday-banner")).toHaveTextContent(
      "Ashadhi Ekadashi",
    );
  });

  it("warns when a lecture's teacher is on leave that day", () => {
    renderView([makeLecture()], {
      leaves: [
        {
          id: "lv1",
          teacher_id: "t1",
          branch_id: "br1",
          start_date: "2026-07-20",
          end_date: "2026-07-22",
          reason: "Medical",
        },
      ],
    });
    expect(screen.getByTestId("day-leave-banner")).toHaveTextContent("Asha");
    expect(screen.getByText("Teacher on leave")).toBeInTheDocument();
  });

  it("marks a covered lecture as a substitute", () => {
    renderView([makeLecture({ actual_teacher_id: "t2" })]);
    const row = screen.getByTestId("day-lecture");
    expect(row).toHaveTextContent("Substitute");
    expect(row).toHaveTextContent("Ravi Deshmukh");
  });

  it("fires day navigation callbacks", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();
    const onPrev = vi.fn();
    const onToday = vi.fn();
    renderView([], { onNext, onPrev, onToday });
    await user.click(screen.getByRole("button", { name: /next/i }));
    await user.click(screen.getByRole("button", { name: /prev/i }));
    await user.click(screen.getByRole("button", { name: /today/i }));
    expect(onNext).toHaveBeenCalled();
    expect(onPrev).toHaveBeenCalled();
    expect(onToday).toHaveBeenCalled();
  });

  describe("now indicator", () => {
    beforeEach(() => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
    });
    afterEach(() => {
      vi.useRealTimers();
    });

    it("renders the now line when the shown day is today", () => {
      vi.setSystemTime(new Date(2026, 6, 21, 10, 30));
      renderView([makeLecture()]);
      expect(screen.getByTestId("day-now-line")).toBeInTheDocument();
    });

    it("omits the now line on any other day", () => {
      vi.setSystemTime(new Date(2026, 6, 25, 10, 30));
      renderView([makeLecture()]);
      expect(screen.queryByTestId("day-now-line")).not.toBeInTheDocument();
    });
  });
});
