import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CourseTable } from "@/app/(dashboard)/courses/_components/course-table";
import type { CourseResponse } from "@/app/(dashboard)/courses/_schemas/course";

const MOCK_COURSES: CourseResponse[] = [
  {
    id: "c1",
    branch_id: "br1",
    academic_year_id: "ay1",
    name: "Physics",
    code: "PHY",
    description: "Mechanics & Waves",
    status: "active",
  },
  {
    id: "c2",
    branch_id: "br1",
    academic_year_id: "ay1",
    name: "Chemistry",
    code: "CHM",
    description: null,
    status: "inactive",
  },
];

describe("CourseTable", () => {
  it("renders table headers", () => {
    render(<CourseTable courses={[]} />);

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Code")).toBeInTheDocument();
    expect(screen.getByText("Description")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("renders course rows with data", () => {
    render(<CourseTable courses={MOCK_COURSES} />);

    expect(screen.getByText("Physics")).toBeInTheDocument();
    expect(screen.getByText("PHY")).toBeInTheDocument();
    expect(screen.getByText("Mechanics & Waves")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("renders em-dash when description is null", () => {
    render(<CourseTable courses={MOCK_COURSES} />);

    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders both status variants", () => {
    render(<CourseTable courses={MOCK_COURSES} />);

    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("inactive")).toBeInTheDocument();
  });

  it("renders empty tbody when no courses", () => {
    const { container } = render(<CourseTable courses={[]} />);
    const rows = container.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(0);
  });
});
