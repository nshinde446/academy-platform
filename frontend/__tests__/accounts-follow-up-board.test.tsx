import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FollowUpDashboard, FollowUpRow } from "@/app/(dashboard)/accounts/_schemas/fees";

function row(partial: Partial<FollowUpRow>): FollowUpRow {
  return {
    student_id: "s1", profile_id: "p1", name: "Aarav Patil", prn: "PRN2514",
    phone: "9800000021", batch: "JEE-B", installment_id: "i1", installment_number: 2,
    due_date: "2026-11-01", amount_due: 25000, days_overdue: 0,
    last_remark: null, last_remark_date: null, ...partial,
  };
}

const DASH: FollowUpDashboard = {
  day: "2026-11-01",
  dues: [row({ student_id: "s1", installment_id: "i1", name: "Aarav Patil" })],
  commitments: [row({ student_id: "s2", installment_id: "i2", name: "Karan Shah", amount_due: 15000 })],
  overdue: [row({ student_id: "s3", installment_id: "i3", name: "Omkar More", due_date: "2026-09-20", days_overdue: 42, amount_due: 20000 })],
  dues_total: 25000, commitments_total: 15000, overdue_total: 20000,
};

const recordPayment = vi.fn().mockResolvedValue({});

vi.mock("@/app/(dashboard)/accounts/_hooks/use-fees", () => ({
  useFollowUp: () => ({ data: DASH, isLoading: false, isError: false }),
  useRecordPayment: () => ({ mutateAsync: recordPayment, isPending: false }),
  useAddRemark: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

import { FollowUpBoard } from "@/app/(dashboard)/accounts/_components/follow-up-board";

describe("FollowUpBoard", () => {
  it("renders the three lists with their rows and totals", () => {
    render(<FollowUpBoard branchId="br1" onOpenProfile={vi.fn()} />);
    expect(screen.getByText("A. Today's Dues")).toBeInTheDocument();
    expect(screen.getByText("B. Today's Commitments")).toBeInTheDocument();
    expect(screen.getByText(/C. Overdue/)).toBeInTheDocument();
    expect(screen.getByText("Aarav Patil")).toBeInTheDocument();
    expect(screen.getByText("Karan Shah")).toBeInTheDocument();
    expect(screen.getByText("Omkar More")).toBeInTheDocument();
    // Overdue row shows the days overdue.
    const overdueRow = screen.getByText("Omkar More").closest("tr")!;
    expect(within(overdueRow).getByText("42")).toBeInTheDocument();
  });

  it("opens the student profile when a name is clicked", async () => {
    const onOpen = vi.fn();
    const user = userEvent.setup();
    render(<FollowUpBoard branchId="br1" onOpenProfile={onOpen} />);
    await user.click(screen.getByText("Aarav Patil"));
    expect(onOpen).toHaveBeenCalledWith("s1");
  });

  it("opens the payment dialog from Mark paid", async () => {
    const user = userEvent.setup();
    render(<FollowUpBoard branchId="br1" onOpenProfile={vi.fn()} />);
    const duesRow = screen.getByText("Aarav Patil").closest("tr")!;
    await user.click(within(duesRow).getByRole("button", { name: /mark paid/i }));
    expect(await screen.findByText(/record payment/i)).toBeInTheDocument();
  });
});
