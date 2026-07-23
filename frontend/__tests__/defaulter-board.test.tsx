import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { DefaulterBoard } from "@/app/(dashboard)/attendance/_components/defaulter-board";
import type { DefaulterRow } from "@/app/(dashboard)/attendance/_schemas/attendance";

const defaultersMock = vi.fn();

vi.mock("@/app/(dashboard)/attendance/_hooks/use-attendance", () => ({
  useDefaulters: (...args: unknown[]) => defaultersMock(...args),
}));

function row(over: Partial<DefaulterRow>): DefaulterRow {
  return {
    student_id: "s1",
    name: "Aarav Patil",
    enrollment_number: "EN-1",
    batches: ["JEE-12-A"],
    present: 6,
    working_days: 10,
    attendance_pct: 60,
    ...over,
  };
}

function setResult(over: {
  data?: DefaulterRow[];
  isLoading?: boolean;
  isError?: boolean;
}) {
  defaultersMock.mockReturnValue({
    data: over.data,
    isLoading: over.isLoading ?? false,
    isError: over.isError ?? false,
  });
}

describe("DefaulterBoard", () => {
  beforeEach(() => {
    defaultersMock.mockReset();
  });

  it("lists defaulters with batch, present count, %, and a summary", () => {
    setResult({
      data: [
        row({ student_id: "s1", name: "Aarav Patil", attendance_pct: 60 }),
        row({ student_id: "s2", name: "Diya Shah", enrollment_number: "EN-2", batches: ["NEET-11-A"], present: 4, working_days: 10, attendance_pct: 40 }),
      ],
    });
    render(<DefaulterBoard branchId="br1" />);

    const table = screen.getByRole("table");
    expect(within(table).getByText("Aarav Patil")).toBeInTheDocument();
    expect(within(table).getByText("Diya Shah")).toBeInTheDocument();
    expect(within(table).getByText("JEE-12-A")).toBeInTheDocument();
    // Scoped to the table — the threshold <select> also renders "60%"/"40%".
    expect(within(table).getByText("60%")).toBeInTheDocument();
    expect(within(table).getByText("40%")).toBeInTheDocument();
    expect(screen.getByText("2 students below 75%")).toBeInTheDocument();
    // The row links to the student's detail page for follow-up.
    expect(screen.getByRole("link", { name: /Aarav Patil/ })).toHaveAttribute(
      "href",
      "/students/s1",
    );
  });

  it("shows a positive empty state when nobody is below the threshold", () => {
    setResult({ data: [] });
    render(<DefaulterBoard branchId="br1" />);
    expect(
      screen.getByText(/No students below 75% in this range/),
    ).toBeInTheDocument();
  });

  it("requeries when the threshold changes", () => {
    setResult({ data: [] });
    render(<DefaulterBoard branchId="br1" />);

    // Initially queried at the default 75% threshold (4th positional arg).
    expect(defaultersMock).toHaveBeenLastCalledWith("br1", expect.any(String), expect.any(String), 75);

    fireEvent.change(screen.getByLabelText("Attendance threshold"), {
      target: { value: "60" },
    });
    expect(defaultersMock).toHaveBeenLastCalledWith("br1", expect.any(String), expect.any(String), 60);
    expect(screen.getByText("0 students below 60%")).toBeInTheDocument();
  });

  it("shows a loading indicator while fetching", () => {
    setResult({ isLoading: true });
    render(<DefaulterBoard branchId="br1" />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });
});
