import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StudentTable } from "@/app/(dashboard)/students/_components/student-table";
import type { StudentWithStats } from "@/app/(dashboard)/students/_schemas/student";

const mockEdit = vi.fn();
const mockDelete = vi.fn();
const mockStream = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
});

const ROWS: StudentWithStats[] = [
  {
    id: "s1",
    first_name: "Rahul",
    last_name: "Sharma",
    enrollment_number: "ROLL-001",
    standard: "11",
    target_exam: "NEET",
    stream: "PCB",
    batch_id: "b1",
    batch_name: "NEET 2025-A",
    fees_status: "paid",
    avg_score_pct: 82,
    attendance_pct: 95,
    dpp_completion_pct: 80,
    batch_rank: 1,
    batch_size: 4,
    tests_taken: 3,
  },
  {
    id: "s2",
    first_name: "Priya",
    last_name: "Patel",
    enrollment_number: null,
    standard: null,
    target_exam: null,
    stream: null,
    batch_id: null,
    batch_name: null,
    fees_status: "overdue",
    avg_score_pct: 45,
    attendance_pct: 0,
    dpp_completion_pct: 0,
    batch_rank: null,
    batch_size: 0,
    tests_taken: 0,
  },
];


describe("StudentTable (MSA_Design layout)", () => {
  it("renders the new analytics headers (Rank, Avg score, Attendance, DPP, Fees)", () => {
    render(
      <StudentTable
        rows={[]}
        onEdit={mockEdit}
        onDelete={mockDelete}
        onStreamChange={mockStream}
      />,
    );

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Rank")).toBeInTheDocument();
    expect(screen.getByText("Avg score")).toBeInTheDocument();
    expect(screen.getByText("Attendance")).toBeInTheDocument();
    expect(screen.getByText("DPP")).toBeInTheDocument();
    expect(screen.getByText("Fees")).toBeInTheDocument();
  });

  it("renders student rows with batch, rank, score, attendance, and fees badge", () => {
    render(
      <StudentTable
        rows={ROWS}
        onEdit={mockEdit}
        onDelete={mockDelete}
        onStreamChange={mockStream}
      />,
    );

    expect(screen.getByText("Rahul Sharma")).toBeInTheDocument();
    expect(screen.getByText("ROLL-001")).toBeInTheDocument();
    expect(screen.getByText("NEET 2025-A")).toBeInTheDocument();
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();
    expect(screen.getByText("95%")).toBeInTheDocument();
    expect(screen.getByText("Paid")).toBeInTheDocument();
    expect(screen.getByText("Overdue")).toBeInTheDocument();
  });

  it("invokes onEdit with the resolved StudentResponse for the row", async () => {
    const user = userEvent.setup();
    render(
      <StudentTable
        rows={ROWS}
        onEdit={mockEdit}
        onDelete={mockDelete}
        onStreamChange={mockStream}
      />,
    );

    const editButtons = screen.getAllByRole("button", { name: /^edit$/i });
    await user.click(editButtons[0]);
    expect(mockEdit).toHaveBeenCalledWith(ROWS[0]);
  });

  it("invokes onDelete with the resolved StudentResponse for the row", async () => {
    const user = userEvent.setup();
    render(
      <StudentTable
        rows={ROWS}
        onEdit={mockEdit}
        onDelete={mockDelete}
        onStreamChange={mockStream}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: /delete rahul sharma/i }),
    );
    expect(mockDelete).toHaveBeenCalledWith(ROWS[0]);
  });

  it("shows the current stream and saves an inline change", async () => {
    const user = userEvent.setup();
    render(
      <StudentTable
        rows={ROWS}
        onEdit={mockEdit}
        onDelete={mockDelete}
        onStreamChange={mockStream}
      />,
    );

    const select = screen.getByRole("combobox", {
      name: /stream for rahul sharma/i,
    }) as HTMLSelectElement;
    expect(select.value).toBe("PCB"); // current stream shown

    await user.selectOptions(select, "PCM");
    expect(mockStream).toHaveBeenCalledWith(ROWS[0], "PCM");
  });
});
