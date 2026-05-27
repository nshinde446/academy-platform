import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TeacherTable } from "@/app/(dashboard)/teachers/_components/teacher-table";
import type {
  TeacherResponse,
  TeacherWithStats,
} from "@/app/(dashboard)/teachers/_schemas/teacher";

const mockEdit = vi.fn();
const mockDelete = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
});

const ROWS: TeacherWithStats[] = [
  {
    id: "t1",
    first_name: "Rahul",
    last_name: "Sharma",
    qualification: "M.Sc Physics, IIT Bombay",
    years_experience: 8,
    subject_id: "sub1",
    subject_name: "Physics",
    lectures_30d: 12,
    sub_rate_pct: 10,
    avg_outcome_delta_pp: 72,
  },
  {
    id: "t2",
    first_name: "Priya",
    last_name: "Nair",
    qualification: null,
    years_experience: null,
    subject_id: null,
    subject_name: null,
    lectures_30d: 0,
    sub_rate_pct: 0,
    avg_outcome_delta_pp: null,
  },
];

const TEACHERS: Record<string, TeacherResponse> = {
  t1: {
    id: "t1",
    branch_id: "b1",
    user_id: null,
    first_name: "Rahul",
    last_name: "Sharma",
    email: "rahul@example.com",
    phone: "9876543210",
    qualification: "M.Sc Physics, IIT Bombay",
    years_experience: 8,
    status: "active",
  },
  t2: {
    id: "t2",
    branch_id: "b1",
    user_id: null,
    first_name: "Priya",
    last_name: "Nair",
    email: null,
    phone: null,
    qualification: null,
    years_experience: null,
    status: "active",
  },
};

describe("TeacherTable (MSA_Design layout)", () => {
  it("renders the new analytics headers", () => {
    render(
      <TeacherTable
        rows={[]}
        teachersById={{}}
        onEdit={mockEdit}
        onDelete={mockDelete}
      />,
    );

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Subject")).toBeInTheDocument();
    expect(screen.getByText("Years")).toBeInTheDocument();
    expect(screen.getByText("Lectures (30d)")).toBeInTheDocument();
    expect(screen.getByText("Sub rate")).toBeInTheDocument();
    expect(screen.getByText("Avg outcome")).toBeInTheDocument();
  });

  it("renders rows with subject badge, years, lectures, sub rate, outcome", () => {
    render(
      <TeacherTable
        rows={ROWS}
        teachersById={TEACHERS}
        onEdit={mockEdit}
        onDelete={mockDelete}
      />,
    );

    expect(screen.getByText("Rahul Sharma")).toBeInTheDocument();
    expect(screen.getByText("Physics")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("10%")).toBeInTheDocument();
    expect(screen.getByText("72%")).toBeInTheDocument();
  });

  it("falls back to dashes for null subject, years, and outcome", () => {
    render(
      <TeacherTable
        rows={ROWS}
        teachersById={TEACHERS}
        onEdit={mockEdit}
        onDelete={mockDelete}
      />,
    );

    // Priya has nulls for subject + years + outcome → at least 3 dashes.
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });

  it("invokes onEdit/onDelete with the resolved TeacherResponse", async () => {
    const user = userEvent.setup();
    render(
      <TeacherTable
        rows={ROWS}
        teachersById={TEACHERS}
        onEdit={mockEdit}
        onDelete={mockDelete}
      />,
    );

    const editButtons = screen.getAllByRole("button", { name: /^edit$/i });
    await user.click(editButtons[0]);
    expect(mockEdit).toHaveBeenCalledWith(TEACHERS.t1);

    await user.click(
      screen.getByRole("button", { name: /delete rahul sharma/i }),
    );
    expect(mockDelete).toHaveBeenCalledWith(TEACHERS.t1);
  });
});
