import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AttendanceRoster } from "@/app/(dashboard)/attendance/_components/attendance-roster";
import type {
  AttendanceRecord,
  RosterStudent,
} from "@/app/(dashboard)/attendance/_schemas/attendance";

const ROSTER: RosterStudent[] = [
  { id: "s1", first_name: "Aarav", last_name: "Patil", enrollment_number: "EN-1" },
  { id: "s2", first_name: "Diya", last_name: "Shah", enrollment_number: "EN-2" },
];

function record(over: Partial<AttendanceRecord>): AttendanceRecord {
  return {
    id: "r1",
    student_id: "s1",
    lecture_id: "l1",
    attendance_status: "PRESENT",
    marked_at: "2026-06-09T09:00:00Z",
    marked_by: null,
    source: "MANUAL",
    branch_id: "br1",
    status: "active",
    ...over,
  };
}

describe("AttendanceRoster", () => {
  const onMark = vi.fn();

  beforeEach(() => {
    onMark.mockReset();
  });

  it("renders every student with name + PRN", () => {
    render(
      <AttendanceRoster
        roster={ROSTER}
        recordByStudent={new Map()}
        onMark={onMark}
      />,
    );
    expect(screen.getByText("Aarav Patil")).toBeInTheDocument();
    expect(screen.getByText("Diya Shah")).toBeInTheDocument();
    // The enrollment number is labeled "PRN" on the roster sub-line.
    expect(screen.getByText(/PRN\s*EN-1/)).toBeInTheDocument();
  });

  it("shows 'Not marked' for students without a record", () => {
    render(
      <AttendanceRoster
        roster={ROSTER}
        recordByStudent={new Map()}
        onMark={onMark}
      />,
    );
    expect(screen.getAllByText("Not marked")).toHaveLength(2);
  });

  it("reflects an existing status with the matching badge", () => {
    const map = new Map<string, AttendanceRecord>([
      ["s1", record({ student_id: "s1", attendance_status: "LATE", source: "BIOMETRIC" })],
    ]);
    render(
      <AttendanceRoster roster={ROSTER} recordByStudent={map} onMark={onMark} />,
    );
    expect(screen.getByText("Late")).toBeInTheDocument();
    expect(screen.getByText("Biometric")).toBeInTheDocument();
  });

  it("calls onMark with the student id and chosen status", async () => {
    const user = userEvent.setup();
    render(
      <AttendanceRoster
        roster={ROSTER}
        recordByStudent={new Map()}
        onMark={onMark}
      />,
    );
    const group = screen.getByRole("group", {
      name: /mark attendance for aarav patil/i,
    });
    await user.click(within(group).getByTitle("Absent"));
    expect(onMark).toHaveBeenCalledWith("s1", "ABSENT");
  });

  it("disables controls while a row is pending", () => {
    render(
      <AttendanceRoster
        roster={ROSTER}
        recordByStudent={new Map()}
        onMark={onMark}
        pendingStudentId="s1"
      />,
    );
    const group = screen.getByRole("group", {
      name: /mark attendance for aarav patil/i,
    });
    expect(within(group).getByTitle("Present")).toBeDisabled();
  });
});
