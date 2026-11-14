import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within, fireEvent } from "@testing-library/react";
import OpeningBalancesPage from "@/app/(dashboard)/payroll/opening-balances/page";
import type { OpeningBalancesResponse } from "@/hooks/use-payroll";

const openingMock = vi.fn();
const saveMutate = vi.fn().mockResolvedValue({ written: 1 });
const importMutate = vi.fn();

vi.mock("@/store/user-store", () => ({
  useBranchId: () => ({ branchId: "br1" }),
  useRoles: () => ({ hasRole: (r: string) => r === "super_admin" }),
}));

vi.mock("@/hooks/use-payroll", () => ({
  useOpeningBalances: (...a: unknown[]) => openingMock(...a),
  useSetOpeningBalances: () => ({ mutateAsync: saveMutate, isPending: false }),
  useImportOpeningBalances: () => ({ mutateAsync: importMutate, isPending: false }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

function setData(over: Partial<OpeningBalancesResponse> & { isLoading?: boolean }) {
  const data: OpeningBalancesResponse = {
    effective_year: 2026,
    effective_month: 1,
    locked: over.locked ?? false,
    rows: over.rows ?? [
      { staff_id: "s1", emp_code: "91000", name: "Asha Rao", department: "MSA", opening_balance: 3 },
    ],
  };
  openingMock.mockReturnValue({
    data: over.isLoading ? undefined : data,
    isLoading: over.isLoading ?? false,
    isError: false,
    refetch: vi.fn(),
  });
}

describe("OpeningBalancesPage", () => {
  beforeEach(() => {
    openingMock.mockReset();
    saveMutate.mockClear();
  });

  it("lists staff with their current opening balance", () => {
    setData({});
    render(<OpeningBalancesPage />);
    const table = screen.getByRole("table");
    expect(within(table).getByText("Asha Rao")).toBeInTheDocument();
    expect(within(table).getByDisplayValue("3")).toBeInTheDocument();
  });

  it("saves only the rows the admin changed", () => {
    setData({});
    render(<OpeningBalancesPage />);
    const input = screen.getByDisplayValue("3");
    fireEvent.change(input, { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    const now = new Date();
    expect(saveMutate).toHaveBeenCalledWith({
      effective_year: now.getFullYear(),
      effective_month: now.getMonth() + 1,
      entries: [{ staff_id: "s1", balance: 5 }],
    });
  });

  it("locks editing once a month is closed", () => {
    setData({ locked: true });
    render(<OpeningBalancesPage />);
    expect(screen.getByText(/already been closed/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });
});
