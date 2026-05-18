import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
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

describe("CourseTable", () => {
  it("renders table headers", () => {
    render(<CourseTable courses={[]} />);

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Code")).toBeInTheDocument();
    expect(screen.getByText("Duration")).toBeInTheDocument();
    expect(screen.getByText("Description")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("renders course rows including duration", () => {
    render(<CourseTable courses={MOCK_COURSES} />);

    expect(screen.getByText("NEET 2-Year")).toBeInTheDocument();
    expect(screen.getByText("NEET-2Y")).toBeInTheDocument();
    expect(screen.getByText("2 years")).toBeInTheDocument();
    expect(screen.getByText("NEET prep program")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("uses 'year' singular when duration is 1", () => {
    render(<CourseTable courses={MOCK_COURSES} />);

    expect(screen.getByText("1 year")).toBeInTheDocument();
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
