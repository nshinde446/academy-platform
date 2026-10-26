import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import PayrollRequestsPage from "@/app/(dashboard)/payroll/requests/page";
import type { ExtraDayRequestDto } from "@/hooks/use-payroll";

const requestsMock = vi.fn();
const decideMutate = vi.fn().mockResolvedValue({});

vi.mock("@/store/user-store", () => ({
  useBranchId: () => ({ branchId: "br1" }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

vi.mock("@/hooks/use-payroll", () => ({
  useRequests: (...a: unknown[]) => requestsMock(...a),
  useDecideRequest: () => ({ mutateAsync: decideMutate, isPending: false }),
  usePayrollStaff: () => ({ data: [{ id: "s1", emp_code: "91000", first_name: "Asha", last_name: "Rao" }] }),
  useRaiseRequest: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRequestHistory: () => ({ data: [], isLoading: false }),
}));

function req(over: Partial<ExtraDayRequestDto>): ExtraDayRequestDto {
  return {
    id: "r1", staff_id: "s1", source_year: 2026, source_month: 4,
    target_year: 2026, target_month: 5, shortfall_days: 1,
    request_status: "PENDING", requested_by: "u1", decided_by: null, note: null, ...over,
  };
}

describe("PayrollRequestsPage", () => {
  beforeEach(() => {
    requestsMock.mockReset();
    decideMutate.mockClear();
  });

  it("lists pending requests with staff name and a make-up month", () => {
    requestsMock.mockReturnValue({ data: [req({})], isLoading: false, isError: false, refetch: vi.fn() });
    render(<PayrollRequestsPage />);
    const table = screen.getByRole("table");
    expect(within(table).getByText("Asha Rao")).toBeInTheDocument();
    expect(within(table).getByText("Apr 2026")).toBeInTheDocument();
    expect(within(table).getByText("May 2026")).toBeInTheDocument();
    expect(within(table).getByText("PENDING")).toBeInTheDocument();
  });

  it("approves a pending request", () => {
    requestsMock.mockReturnValue({ data: [req({})], isLoading: false, isError: false, refetch: vi.fn() });
    render(<PayrollRequestsPage />);
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(decideMutate).toHaveBeenCalledWith(expect.objectContaining({ id: "r1", verb: "approve" }));
  });

  it("shows an empty state when a tab has no requests", () => {
    requestsMock.mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() });
    render(<PayrollRequestsPage />);
    expect(screen.getByText(/No requests in this tab/)).toBeInTheDocument();
  });
});
