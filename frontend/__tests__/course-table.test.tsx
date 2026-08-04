import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CourseTable } from "@/app/(dashboard)/courses/_components/course-table";
import type { CourseResponse } from "@/app/(dashboard)/courses/_schemas/course";

const MOCK_COURSES: CourseResponse[] = [
  {
    id: "c1",
    branch_id: "br1",
    name: "NEET 2-Year",
    code: "NEET-2Y",
    description: "NEET prep program",
    duration_years: 2,
    status: "active",
  },
  {
    id: "c2",
    branch_id: "br1",
    name: "Class 9",
    code: "C9",
    description: null,
    duration_years: 1,
    status: "inactive",
  },
];

const mockEdit = vi.fn();
const mockDelete = vi.fn();
const mockManage = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CourseTable", () => {
  it("renders table headers", () => {
    render(
      <CourseTable courses={[]} onEdit={mockEdit} onDelete={mockDelete} onManageSubjects={mockManage} />
    );

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Code")).toBeInTheDocument();
    expect(screen.getByText("Duration")).toBeInTheDocument();
    expect(screen.getByText("Description")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Actions")).toBeInTheDocument();
  });

  it("renders course rows including duration", () => {
    render(
      <CourseTable
        courses={MOCK_COURSES}
        onEdit={mockEdit}
        onDelete={mockDelete}
        onManageSubjects={mockManage}
      />
    );

    expect(screen.getByText("NEET 2-Year")).toBeInTheDocument();
    expect(screen.getByText("NEET-2Y")).toBeInTheDocument();
    expect(screen.getByText("2 years")).toBeInTheDocument();
    expect(screen.getByText("NEET prep program")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("uses 'year' singular when duration is 1", () => {
    render(
      <CourseTable
        courses={MOCK_COURSES}
        onEdit={mockEdit}
        onDelete={mockDelete}
        onManageSubjects={mockManage}
      />
    );

    expect(screen.getByText("1 year")).toBeInTheDocument();
  });

  it("renders em-dash when description is null", () => {
    render(
      <CourseTable
        courses={MOCK_COURSES}
        onEdit={mockEdit}
        onDelete={mockDelete}
        onManageSubjects={mockManage}
      />
    );

    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders both status variants", () => {
    render(
      <CourseTable
        courses={MOCK_COURSES}
        onEdit={mockEdit}
        onDelete={mockDelete}
        onManageSubjects={mockManage}
      />
    );

    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("inactive")).toBeInTheDocument();
  });

  it("renders empty tbody when no courses", () => {
    const { container } = render(
      <CourseTable courses={[]} onEdit={mockEdit} onDelete={mockDelete} onManageSubjects={mockManage} />
    );
    const rows = container.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(0);
  });

  it("invokes onEdit with the row's course", async () => {
    const user = userEvent.setup();
    render(
      <CourseTable
        courses={MOCK_COURSES}
        onEdit={mockEdit}
        onDelete={mockDelete}
        onManageSubjects={mockManage}
      />
    );

    const editButtons = screen.getAllByRole("button", { name: /^edit$/i });
    await user.click(editButtons[0]);

    expect(mockEdit).toHaveBeenCalledWith(MOCK_COURSES[0]);
  });

  it("invokes onManageSubjects with the row's course", async () => {
    const user = userEvent.setup();
    render(
      <CourseTable
        courses={MOCK_COURSES}
        onEdit={mockEdit}
        onDelete={mockDelete}
        onManageSubjects={mockManage}
      />
    );

    const subjectButtons = screen.getAllByRole("button", { name: /^subjects$/i });
    await user.click(subjectButtons[0]);

    expect(mockManage).toHaveBeenCalledWith(MOCK_COURSES[0]);
  });

  it("invokes onDelete with the row's course", async () => {
    const user = userEvent.setup();
    render(
      <CourseTable
        courses={MOCK_COURSES}
        onEdit={mockEdit}
        onDelete={mockDelete}
        onManageSubjects={mockManage}
      />
    );

    await user.click(
      screen.getByRole("button", { name: /delete course neet 2-year/i })
    );

    expect(mockDelete).toHaveBeenCalledWith(MOCK_COURSES[0]);
  });
});
