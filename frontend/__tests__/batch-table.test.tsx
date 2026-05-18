import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BatchTable } from "@/app/(dashboard)/batches/_components/batch-table";
import type { BatchResponse } from "@/app/(dashboard)/batches/_schemas/batch";

const MOCK_BATCHES: BatchResponse[] = [
  {
    id: "b1",
    branch_id: "br1",
    academic_year_id: "ay1",
    course_id: "c1",
    name: "Physics Morning",
    code: "PHY-M",
    capacity: 30,
    status: "active",
  },
  {
    id: "b2",
    branch_id: "br1",
    academic_year_id: "ay1",
    course_id: "c2",
    name: "Chemistry Evening",
    code: "CHM-E",
    capacity: 25,
    status: "inactive",
  },
];

describe("BatchTable", () => {
  it("renders table headers", () => {
    render(<BatchTable batches={[]} />);

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Code")).toBeInTheDocument();
    expect(screen.getByText("Capacity")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("renders batch rows with data", () => {
    render(<BatchTable batches={MOCK_BATCHES} />);

    expect(screen.getByText("Physics Morning")).toBeInTheDocument();
    expect(screen.getByText("PHY-M")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("renders correct status badge variants", () => {
    render(<BatchTable batches={MOCK_BATCHES} />);

    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("inactive")).toBeInTheDocument();
  });

  it("renders empty tbody when no batches", () => {
    const { container } = render(<BatchTable batches={[]} />);
    const rows = container.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(0);
  });
});
