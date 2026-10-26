import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import PayrollReportPage from "@/app/(dashboard)/payroll/page";
import type { ReportResponse, ReportRow } from "@/hooks/use-payroll";

const reportMock = vi.fn();
const deptsMock = vi.fn();

vi.mock("@/store/user-store", () => ({
  useBranchId: () => ({ branchId: "br1" }),
}));

vi.mock("@/hooks/use-payroll", () => ({
  usePayrollReport: (...a: unknown[]) => reportMock(...a),
  usePayrollDepartments: (...a: unknown[]) => deptsMock(...a),
  downloadPayroll: vi.fn(),
}));

function row(over: Partial<ReportRow>): ReportRow {
  return {
    staff_id: "s1", emp_code: "91000", name: "Asha Rao", department: "MSA-Teachers",
    required_days: 26, present_days: 27, half_days: 0, paid_leave_days: 0,
    net_days: 1, balance_in: 0, balance_out: 1, uncovered_days: 0,
    deferred_days: 0, late_fine_total: 0, ...over,
  };
}

function setReport(over: Partial<ReportResponse> & { isLoading?: boolean; isError?: boolean }) {
  const data: ReportResponse = {
    year: 2026, month: 6, lifecycle: over.lifecycle ?? "OPEN",
    rows: over.rows ?? [],
    totals: over.totals ?? { staff_count: 0, present_days: 0, uncovered_days: 0, late_fine_total: 0 },
  };
  reportMock.mockReturnValue({
    data: over.isLoading || over.isError ? undefined : data,
    isLoading: over.isLoading ?? false,
    isError: over.isError ?? false,
    refetch: vi.fn(),
  });
}

describe("PayrollReportPage", () => {
  beforeEach(() => {
    reportMock.mockReset();
    deptsMock.mockReset();
    deptsMock.mockReturnValue({ data: [{ id: "d1", name: "MSA-Teachers" }] });
  });

  it("renders rows, net sign and a totals line for an open (preview) month", () => {
    setReport({
      lifecycle: "OPEN",
      rows: [
        row({ staff_id: "s1", name: "Asha Rao", net_days: 1, balance_out: 1 }),
        row({ staff_id: "s2", emp_code: "91001", name: "Ravi Kumar", present_days: 24, net_days: -2, uncovered_days: 2, late_fine_total: 1500 }),
      ],
      totals: { staff_count: 2, present_days: 51, uncovered_days: 2, late_fine_total: 1500 },
    });
    render(<PayrollReportPage />);

    const table = screen.getByRole("table");
    expect(within(table).getByText("Asha Rao")).toBeInTheDocument();
    expect(within(table).getByText("Ravi Kumar")).toBeInTheDocument();
    expect(within(table).getByText("+1")).toBeInTheDocument();
    expect(within(table).getByText("-2")).toBeInTheDocument();
    expect(within(table).getByText(/Totals · 2 staff/)).toBeInTheDocument();
    // An open month is labelled as a preview.
    expect(screen.getByText("Preview")).toBeInTheDocument();
  });

  it("shows a set-up hint when the month is not configured", () => {
    setReport({ lifecycle: "NOT_SET", rows: [] });
    render(<PayrollReportPage />);
    expect(screen.getByText(/has not been set up/)).toBeInTheDocument();
  });

  it("shows the error state on failure", () => {
    setReport({ isError: true });
    render(<PayrollReportPage />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});
