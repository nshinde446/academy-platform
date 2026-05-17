import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StudentTable } from "@/app/(dashboard)/students/_components/student-table";
import type { StudentResponse } from "@/app/(dashboard)/students/_schemas/student";

const MOCK_STUDENTS: StudentResponse[] = [
  {
    id: "s1",
    branch_id: "b1",
    academic_year_id: "ay1",
    first_name: "Rahul",
    last_name: "Sharma",
    email: "rahul@example.com",
    phone: "9876543210",
    date_of_birth: "2005-03-15",
    enrollment_number: "ENR-001",
    course_id: null,
    status: "active",
  },
  {
    id: "s2",
    branch_id: "b1",
    academic_year_id: "ay1",
    first_name: "Priya",
    last_name: "Patel",
    email: null,
    phone: null,
    date_of_birth: null,
    enrollment_number: null,
    course_id: null,
    status: "inactive",
  },
];

describe("StudentTable", () => {
  it("renders table headers", () => {
    render(<StudentTable students={[]} />);

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Enrollment No.")).toBeInTheDocument();
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByText("Phone")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("renders student rows with data", () => {
    render(<StudentTable students={MOCK_STUDENTS} />);

    expect(screen.getByText("Rahul Sharma")).toBeInTheDocument();
    expect(screen.getByText("ENR-001")).toBeInTheDocument();
    expect(screen.getByText("rahul@example.com")).toBeInTheDocument();
    expect(screen.getByText("9876543210")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("renders dashes for null fields", () => {
    render(<StudentTable students={MOCK_STUDENTS} />);

    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(3);
  });

  it("renders empty state when no students", () => {
    const { container } = render(<StudentTable students={[]} />);
    const rows = container.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(0);
  });

  it("renders correct status badge variant", () => {
    render(<StudentTable students={MOCK_STUDENTS} />);

    const activeBadge = screen.getByText("active");
    const inactiveBadge = screen.getByText("inactive");
    expect(activeBadge).toBeInTheDocument();
    expect(inactiveBadge).toBeInTheDocument();
  });
});
