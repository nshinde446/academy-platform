import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BatchTable } from "@/app/(dashboard)/batches/_components/batch-table";
import type {
  AcademicYearResponse,
  BatchResponse,
  CourseResponse,
} from "@/app/(dashboard)/batches/_schemas/batch";

const MOCK_COURSES: CourseResponse[] = [
  {
    id: "c1",
    branch_id: "br1",
    name: "NEET 2-Year",
    code: "NEET-2Y",
    description: null,
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
    status: "active",
  },
];

const MOCK_YEARS: AcademicYearResponse[] = [
  {
    id: "ay1",
    branch_id: "br1",
    name: "2025-2026",
    start_year: 2025,
    end_year: 2026,
    status: "active",
  },
  {
    id: "ay2",
    branch_id: "br1",
    name: "2026-2027",
    start_year: 2026,
    end_year: 2027,
    status: "active",
  },
];

const MOCK_BATCHES: BatchResponse[] = [
  {
    id: "b1",
    branch_id: "br1",
    start_academic_year_id: "ay1",
    end_academic_year_id: "ay2",
    course_id: "c1",
    name: "NEET 2025-2027 A",
    code: "NEET-A",
    capacity: 30,
    duration_years: 2,
    status: "active",
  },
  {
    id: "b2",
    branch_id: "br1",
    start_academic_year_id: "ay1",
    end_academic_year_id: "ay1",
    course_id: "c2",
    name: "Class 9 A",
    code: "C9-A",
    capacity: 25,
    duration_years: 1,
    status: "inactive",
  },
];

describe("BatchTable", () => {
  it("renders table headers", () => {
    render(<BatchTable batches={[]} courses={MOCK_COURSES} academicYears={MOCK_YEARS} />);

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Course")).toBeInTheDocument();
    expect(screen.getByText("Duration")).toBeInTheDocument();
    expect(screen.getByText("Academic Years")).toBeInTheDocument();
    expect(screen.getByText("Capacity")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("renders the 2-year academic year range", () => {
    render(
      <BatchTable
        batches={MOCK_BATCHES}
        courses={MOCK_COURSES}
        academicYears={MOCK_YEARS}
      />
    );

    expect(screen.getByText("NEET 2025-2027 A")).toBeInTheDocument();
    expect(screen.getByText("NEET 2-Year")).toBeInTheDocument();
    expect(screen.getByText("2 years")).toBeInTheDocument();
    expect(screen.getByText("2025-2026 → 2026-2027")).toBeInTheDocument();
  });

  it("shows a single year when start == end", () => {
    render(
      <BatchTable
        batches={MOCK_BATCHES}
        courses={MOCK_COURSES}
        academicYears={MOCK_YEARS}
      />
    );

    expect(screen.getByText("Class 9 A")).toBeInTheDocument();
    expect(screen.getByText("Class 9")).toBeInTheDocument();
    expect(screen.getByText("1 year")).toBeInTheDocument();
    expect(screen.getByText("2025-2026")).toBeInTheDocument();
  });

  it("renders correct status badge variants", () => {
    render(
      <BatchTable
        batches={MOCK_BATCHES}
        courses={MOCK_COURSES}
        academicYears={MOCK_YEARS}
      />
    );

    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("inactive")).toBeInTheDocument();
  });

  it("renders empty tbody when no batches", () => {
    const { container } = render(
      <BatchTable
        batches={[]}
        courses={MOCK_COURSES}
        academicYears={MOCK_YEARS}
      />
    );
    const rows = container.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(0);
  });
});
