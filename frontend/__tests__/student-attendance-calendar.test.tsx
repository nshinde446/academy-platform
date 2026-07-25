import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { StudentAttendanceCalendar } from "@/app/(dashboard)/students/[studentId]/_components/attendance-calendar";
import type {
  AttendanceSummary,
  DailyAttendance,
} from "@/app/(dashboard)/attendance/_schemas/attendance";

const timelineMock = vi.fn();
const summaryMock = vi.fn();

// Both hooks resolve to the same module the component imports relatively; vitest
// keys the mock on the resolved path, so the alias specifier intercepts it.
vi.mock("@/app/(dashboard)/attendance/_hooks/use-attendance", () => ({
  useStudentTimeline: (...args: unknown[]) => timelineMock(...args),
  useAttendanceSummary: (...args: unknown[]) => summaryMock(...args),
}));

function dayRow(over: Partial<DailyAttendance>): DailyAttendance {
  return {
    id: "d1",
    student_id: "stu1",
    branch_id: "br1",
    attendance_date: "2026-07-10",
    first_in: "2026-07-10T03:59:00Z",
    last_out: "2026-07-10T10:00:00Z",
    day_status: "PRESENT",
    signoff: "COMPLETE",
    source: "BIOMETRIC",
    ...over,
  };
}

function setHooks(rows: DailyAttendance[], summary: AttendanceSummary | undefined) {
  timelineMock.mockReturnValue({ data: rows, isLoading: false });
  summaryMock.mockReturnValue({ data: summary, isLoading: false });
}

describe("StudentAttendanceCalendar", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 6, 15)); // 15 Jul 2026, local
    timelineMock.mockReset();
    summaryMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the current month with the canonical summary %", () => {
    setHooks(
      [
        dayRow({ attendance_date: "2026-07-10", day_status: "PRESENT" }),
        dayRow({ attendance_date: "2026-07-11", day_status: "ABSENT", first_in: null, last_out: null, signoff: "NA" }),
      ],
      { student_id: "stu1", working_days: 2, present_days: 1, absent_days: 1, attendance_pct: 50 },
    );
    render(<StudentAttendanceCalendar branchId="br1" studentId="stu1" />);

    expect(screen.getByText("July 2026")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("1/2 days")).toBeInTheDocument();
    // Day cells carry the status (and times) in their title for hover.
    expect(screen.getByTitle(/2026-07-10 · PRESENT/)).toBeInTheDocument();
    expect(screen.getByTitle(/2026-07-11 · ABSENT/)).toBeInTheDocument();
  });

  it("navigates to the previous month and requeries its range", () => {
    setHooks([], { student_id: "stu1", working_days: 0, present_days: 0, absent_days: 0, attendance_pct: 0 });
    render(<StudentAttendanceCalendar branchId="br1" studentId="stu1" />);

    fireEvent.click(screen.getByLabelText("Previous month"));
    expect(screen.getByText("June 2026")).toBeInTheDocument();
    // The timeline hook was called with a June range.
    expect(timelineMock).toHaveBeenCalledWith("br1", "stu1", "2026-06-01", "2026-06-30");
  });

  it("shows a fallback when there are no working days in range", () => {
    setHooks([], { student_id: "stu1", working_days: 0, present_days: 0, absent_days: 0, attendance_pct: 0 });
    render(<StudentAttendanceCalendar branchId="br1" studentId="stu1" />);
    expect(screen.getByText("No working days")).toBeInTheDocument();
  });

  it("disables next-month navigation at the current month", () => {
    setHooks([], undefined);
    render(<StudentAttendanceCalendar branchId="br1" studentId="stu1" />);
    expect(screen.getByLabelText("Next month")).toBeDisabled();
  });

  it("switches to the day log and shows exact IN/OUT times and a window", () => {
    setHooks(
      [
        dayRow({
          attendance_date: "2026-07-10",
          day_status: "PRESENT",
          first_in: "2026-07-10T03:58:00Z", // 09:28 IST
          last_out: "2026-07-10T10:32:00Z", // 16:02 IST
          signoff: "COMPLETE",
        }),
      ],
      { student_id: "stu1", working_days: 1, present_days: 1, absent_days: 0, attendance_pct: 100 },
    );
    render(<StudentAttendanceCalendar branchId="br1" studentId="stu1" />);

    fireEvent.click(screen.getByRole("button", { name: "log" }));

    // Column headers of the reviewable roster.
    expect(screen.getByText("In")).toBeInTheDocument();
    expect(screen.getByText("Out")).toBeInTheDocument();
    expect(screen.getByText("Sign-off")).toBeInTheDocument();
    // The on-campus window: 03:58Z → 10:32Z is 6h34, timezone-independent.
    expect(screen.getByText("6h34")).toBeInTheDocument();
    expect(screen.getByText("Complete")).toBeInTheDocument();
  });

  it("flags a missing sign-off and dashes an absent day's times in the log", () => {
    setHooks(
      [
        dayRow({
          attendance_date: "2026-07-09",
          day_status: "PRESENT",
          first_in: "2026-07-09T03:58:00Z",
          last_out: null,
          signoff: "MISSING",
        }),
        dayRow({
          id: "d2",
          attendance_date: "2026-07-08",
          day_status: "ABSENT",
          first_in: null,
          last_out: null,
          signoff: "NA",
        }),
      ],
      { student_id: "stu1", working_days: 2, present_days: 1, absent_days: 1, attendance_pct: 50 },
    );
    render(<StudentAttendanceCalendar branchId="br1" studentId="stu1" />);
    fireEvent.click(screen.getByRole("button", { name: "log" }));

    expect(screen.getByText("Missing")).toBeInTheDocument();
    expect(screen.getByText("Absent")).toBeInTheDocument();
    // Absent day has no times → dashes (both cells and its window).
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(2);
  });
});
