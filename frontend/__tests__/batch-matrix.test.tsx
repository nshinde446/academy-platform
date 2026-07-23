import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { BatchMatrix } from "@/app/(dashboard)/attendance/_components/batch-matrix";
import type { BatchMatrix as BatchMatrixData } from "@/app/(dashboard)/attendance/_schemas/attendance";

const matrixMock = vi.fn();

vi.mock("@/app/(dashboard)/attendance/_hooks/use-attendance", () => ({
  useBatchMatrix: (...args: unknown[]) => matrixMock(...args),
}));

const BATCHES = [
  { id: "b1", name: "JEE-12-A" },
  { id: "b2", name: "NEET-11-A" },
];

function setResult(over: {
  data?: BatchMatrixData;
  isLoading?: boolean;
  isError?: boolean;
}) {
  matrixMock.mockReturnValue({
    data: over.data,
    isLoading: over.isLoading ?? false,
    isError: over.isError ?? false,
  });
}

const MATRIX: BatchMatrixData = {
  batch_id: "b1",
  dates: ["2026-07-10", "2026-07-11"],
  students: [
    {
      student_id: "s1",
      name: "Aarav Patil",
      enrollment_number: "EN-1",
      cells: ["P", "A"],
      present: 1,
      working_days: 2,
      attendance_pct: 50,
    },
  ],
  day_present: [1, 0],
  student_count: 1,
};

describe("BatchMatrix", () => {
  beforeEach(() => {
    matrixMock.mockReset();
  });

  it("prompts to pick a batch before anything is selected", () => {
    setResult({ data: undefined });
    render(<BatchMatrix branchId="br1" batches={BATCHES} />);
    expect(
      screen.getByText(/Pick a batch to see its month attendance matrix/),
    ).toBeInTheDocument();
  });

  it("renders the students × days grid with per-student % and day totals", () => {
    setResult({ data: MATRIX });
    render(<BatchMatrix branchId="br1" batches={BATCHES} />);
    // Select a batch so the grid renders.
    fireEvent.change(screen.getByLabelText("Select batch"), {
      target: { value: "b1" },
    });

    const table = screen.getByRole("table");
    expect(within(table).getByText("Aarav Patil")).toBeInTheDocument();
    // P/L/A cells for the row.
    expect(within(table).getByText("P")).toBeInTheDocument();
    expect(within(table).getByText("A")).toBeInTheDocument();
    // Per-student range %.
    expect(within(table).getByText("50%")).toBeInTheDocument();
    // Day columns (day-of-month) and the present-per-day footer.
    expect(within(table).getByText("10")).toBeInTheDocument();
    expect(within(table).getByText("11")).toBeInTheDocument();
    expect(within(table).getByText("Present / 1")).toBeInTheDocument();
  });

  it("queries with the selected batch id", () => {
    setResult({ data: MATRIX });
    render(<BatchMatrix branchId="br1" batches={BATCHES} />);
    fireEvent.change(screen.getByLabelText("Select batch"), {
      target: { value: "b2" },
    });
    expect(matrixMock).toHaveBeenLastCalledWith(
      "br1",
      "b2",
      expect.any(String),
      expect.any(String),
    );
  });

  it("shows a fallback when the batch has no scheduled lectures in range", () => {
    setResult({
      data: { ...MATRIX, dates: [], students: [], day_present: [] },
    });
    render(<BatchMatrix branchId="br1" batches={BATCHES} />);
    fireEvent.change(screen.getByLabelText("Select batch"), {
      target: { value: "b1" },
    });
    expect(
      screen.getByText(/No scheduled lectures for this batch in the selected range/),
    ).toBeInTheDocument();
  });
});
