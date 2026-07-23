import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { InstituteOverview } from "@/app/(dashboard)/attendance/_components/institute-overview";
import type { BranchSummaryRow } from "@/app/(dashboard)/attendance/_schemas/attendance";

const summaryMock = vi.fn();

vi.mock("@/app/(dashboard)/attendance/_hooks/use-attendance", () => ({
  useBranchSummary: (...args: unknown[]) => summaryMock(...args),
}));

function batch(over: Partial<BranchSummaryRow>): BranchSummaryRow {
  return {
    batch_id: "b1",
    batch_name: "JEE-12-A",
    batch_code: "J12A",
    student_count: 10,
    working_days: 1,
    present: 8,
    total_slots: 10,
    avg_pct: 80,
    ...over,
  };
}

function setResult(over: {
  data?: BranchSummaryRow[];
  isLoading?: boolean;
  isError?: boolean;
}) {
  summaryMock.mockReturnValue({
    data: over.data,
    isLoading: over.isLoading ?? false,
    isError: over.isError ?? false,
  });
}

describe("InstituteOverview", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 6, 23)); // 23 Jul 2026, local
    summaryMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("rolls up in-session batches into headline present % and lists them", () => {
    setResult({
      data: [
        batch({ batch_id: "b1", batch_name: "JEE-12-A", present: 8, total_slots: 10, avg_pct: 80 }),
        batch({ batch_id: "b2", batch_name: "NEET-11-A", student_count: 10, present: 5, total_slots: 10, avg_pct: 50 }),
      ],
    });
    render(<InstituteOverview branchId="br1" />);

    // 13 present of 20 slots = 65% headline.
    expect(screen.getByText("65%")).toBeInTheDocument();
    expect(screen.getByText("13/20")).toBeInTheDocument();
    // Batches-in-session KPI — scoped to its own tile (value "2" is not unique).
    const batchesKpi = screen.getByText("Batches in session").parentElement!;
    expect(within(batchesKpi).getByText("2")).toBeInTheDocument();

    const table = screen.getByRole("table");
    expect(within(table).getByText("JEE-12-A")).toBeInTheDocument();
    expect(within(table).getByText("NEET-11-A")).toBeInTheDocument();
    // Worst-first: NEET (50%) ahead of JEE (80%).
    const rows = within(table).getAllByRole("row").slice(1); // drop header
    expect(within(rows[0]).getByText("NEET-11-A")).toBeInTheDocument();
    expect(within(rows[1]).getByText("JEE-12-A")).toBeInTheDocument();
  });

  it("excludes batches with no session that day from the headline", () => {
    setResult({
      data: [
        batch({ batch_id: "b1", batch_name: "In session", present: 9, total_slots: 10, avg_pct: 90, working_days: 1 }),
        batch({ batch_id: "b2", batch_name: "No session", present: 0, total_slots: 0, avg_pct: 0, working_days: 0 }),
      ],
    });
    render(<InstituteOverview branchId="br1" />);

    // Headline + the single in-session row both read 90% (the no-session batch
    // is excluded from the rollup).
    expect(screen.getAllByText("90%")).toHaveLength(2);
    expect(screen.getByText(/1 batch not in session this day/)).toBeInTheDocument();
    expect(screen.queryByText("No session")).not.toBeInTheDocument();
  });

  it("shows a fallback when no batch is in session", () => {
    setResult({ data: [batch({ working_days: 0, total_slots: 0, avg_pct: 0 })] });
    render(<InstituteOverview branchId="br1" />);
    expect(
      screen.getByText(/No batch has a scheduled session on this day/),
    ).toBeInTheDocument();
  });
});
