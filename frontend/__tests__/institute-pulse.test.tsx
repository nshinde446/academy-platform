import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { InstitutePulse } from "@/app/(dashboard)/attendance/_components/institute-pulse";
import type { BranchSummaryRow } from "@/app/(dashboard)/attendance/_schemas/attendance";

const summaryMock = vi.fn();

vi.mock("@/app/(dashboard)/attendance/_hooks/use-attendance", () => ({
  useBranchSummary: (...args: unknown[]) => summaryMock(...args),
}));

function batch(over: Partial<BranchSummaryRow>): BranchSummaryRow {
  return {
    batch_id: "b1",
    batch_name: "JEE-12-A",
    batch_code: null,
    student_count: 10,
    working_days: 1,
    present: 8,
    total_slots: 10,
    avg_pct: 80,
    ...over,
  };
}

function setResult(data: BranchSummaryRow[] | undefined, isLoading = false) {
  summaryMock.mockReturnValue({ data, isLoading, isError: false });
}

describe("InstitutePulse", () => {
  beforeEach(() => summaryMock.mockReset());

  it("rolls up in-session batches and shows the defaulter count", () => {
    setResult([
      batch({ batch_id: "b1", present: 8, total_slots: 10 }),
      batch({ batch_id: "b2", present: 5, total_slots: 10 }),
    ]);
    render(
      <InstitutePulse
        branchId="br1"
        today="2026-07-23"
        defaultersCount={3}
        defaultersLoading={false}
      />,
    );
    // 13 present of 20 slots = 65%.
    expect(screen.getByText("65%")).toBeInTheDocument();
    expect(screen.getByText("13 / 20")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument(); // absent
    expect(screen.getByText("2")).toBeInTheDocument(); // batches in session
    expect(screen.getByText("3")).toBeInTheDocument(); // defaulters (from prop)
  });

  it("falls back cleanly when no batch is in session today", () => {
    setResult([]);
    render(
      <InstitutePulse
        branchId="br1"
        today="2026-07-23"
        defaultersCount={0}
        defaultersLoading={false}
      />,
    );
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("no session today")).toBeInTheDocument();
  });
});
