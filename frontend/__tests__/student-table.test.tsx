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
    enrollment_number: "ROLL-001",
    parent_mobile: "9123456789",
    rfid_number: "RFID-AAA-001",
    gender: "M",
    district: "Pune",
    caste: null,
    username: null,
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
    parent_mobile: null,
    rfid_number: null,
    gender: null,
    district: null,
    caste: null,
    username: null,
    course_id: null,
    status: "inactive",
  },
];

describe("StudentTable", () => {
  it("renders table headers including Roll No, Gender, Parent Mobile, RFID", () => {
    render(<StudentTable students={[]} />);

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Roll No")).toBeInTheDocument();
    expect(screen.getByText("Gender")).toBeInTheDocument();
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByText("Phone")).toBeInTheDocument();
    expect(screen.getByText("Parent Mobile")).toBeInTheDocument();
    expect(screen.getByText("RFID")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("no longer renders the old 'Enrollment No.' header", () => {
    render(<StudentTable students={[]} />);
    expect(screen.queryByText("Enrollment No.")).not.toBeInTheDocument();
  });

  it("renders student rows with all data including gender, parent_mobile and rfid_number", () => {
    render(<StudentTable students={MOCK_STUDENTS} />);

    expect(screen.getByText("Rahul Sharma")).toBeInTheDocument();
    expect(screen.getByText("ROLL-001")).toBeInTheDocument();
    expect(screen.getByText("M")).toBeInTheDocument();
    expect(screen.getByText("rahul@example.com")).toBeInTheDocument();
    expect(screen.getByText("9876543210")).toBeInTheDocument();
    expect(screen.getByText("9123456789")).toBeInTheDocument();
    expect(screen.getByText("RFID-AAA-001")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("renders dashes for null optional fields", () => {
    render(<StudentTable students={MOCK_STUDENTS} />);

    // Priya has 6 null displayed fields (enrollment, gender, email, phone, parent_mobile, rfid)
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(6);
  });

  it("renders empty state when no students", () => {
    const { container } = render(<StudentTable students={[]} />);
    const rows = container.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(0);
  });

  it("renders correct status badge variant", () => {
    render(<StudentTable students={MOCK_STUDENTS} />);

    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("inactive")).toBeInTheDocument();
  });
});
