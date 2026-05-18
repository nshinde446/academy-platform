import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AcademicYearTable } from "@/app/(dashboard)/academic-years/_components/academic-year-table";
import type { AcademicYearResponse } from "@/app/(dashboard)/academic-years/_schemas/academic-year";

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
    status: "inactive",
  },
];

const mockDelete = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AcademicYearTable", () => {
  it("renders table headers", () => {
    render(<AcademicYearTable academicYears={[]} onDelete={mockDelete} />);

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Start")).toBeInTheDocument();
    expect(screen.getByText("End")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Actions")).toBeInTheDocument();
  });

  it("renders year rows", () => {
    render(
      <AcademicYearTable academicYears={MOCK_YEARS} onDelete={mockDelete} />
    );

    expect(screen.getByText("2025-2026")).toBeInTheDocument();
    expect(screen.getByText("2025")).toBeInTheDocument();
    expect(screen.getByText("2026-2027")).toBeInTheDocument();
    expect(screen.getByText("2027")).toBeInTheDocument();
  });

  it("renders both status badges", () => {
    render(
      <AcademicYearTable academicYears={MOCK_YEARS} onDelete={mockDelete} />
    );

    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("inactive")).toBeInTheDocument();
  });

  it("renders empty tbody when no years", () => {
    const { container } = render(
      <AcademicYearTable academicYears={[]} onDelete={mockDelete} />
    );
    const rows = container.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(0);
  });

  it("has no Edit button (years are immutable)", () => {
    render(
      <AcademicYearTable academicYears={MOCK_YEARS} onDelete={mockDelete} />
    );

    expect(screen.queryByRole("button", { name: /^edit$/i })).toBeNull();
  });

  it("attaches the immutable-edit tooltip on each row", () => {
    const { container } = render(
      <AcademicYearTable academicYears={MOCK_YEARS} onDelete={mockDelete} />
    );

    const rows = container.querySelectorAll("tbody tr");
    rows.forEach((row) => {
      expect(row.getAttribute("title")).toMatch(/immutable/i);
    });
  });

  it("invokes onDelete with the row's year", async () => {
    const user = userEvent.setup();
    render(
      <AcademicYearTable academicYears={MOCK_YEARS} onDelete={mockDelete} />
    );

    await user.click(
      screen.getByRole("button", { name: /delete academic year 2025-2026/i })
    );

    expect(mockDelete).toHaveBeenCalledWith(MOCK_YEARS[0]);
  });
});
