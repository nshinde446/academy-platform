import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { StaffDayRegisterRow } from "@/app/(dashboard)/attendance/_schemas/staff-attendance";

const ROWS: StaffDayRegisterRow[] = [
  {
    staff_id: "st1", emp_code: "12", name: "Rahul Pawar", department: "MSA-Teachers",
    in_time: "09:45", out_time: "17:35", work_minutes: 470, ot_minutes: 0,
    status: "PRESENT", missed_signoff: false,
    entry_type: "MANUAL", marked_by: "Admin User (Super Admin)", marked_at: "13:00",
  },
  {
    staff_id: "st2", emp_code: "13", name: "Sneha Rao", department: "MSA-Teachers",
    in_time: "10:02", out_time: null, work_minutes: 0, ot_minutes: 0,
    status: "LATE", missed_signoff: true,
    entry_type: "BIOMETRIC", marked_by: null, marked_at: null,
  },
  {
    staff_id: "st3", emp_code: "14", name: "Vivek Jain", department: "MSA-Teachers",
    in_time: null, out_time: null, work_minutes: 0, ot_minutes: 0,
    status: "ABSENT", missed_signoff: false,
    entry_type: null, marked_by: null, marked_at: null,
  },
];

const manualMark = vi.fn().mockResolvedValue({});

vi.mock("@/app/(dashboard)/attendance/_hooks/use-staff-attendance", () => ({
  useStaffDayRegister: () => ({ data: ROWS, isLoading: false, isError: false }),
  useStaffManualMark: () => ({ mutateAsync: manualMark, isPending: false }),
}));

vi.mock("@/app/(dashboard)/staff/_hooks/use-staff", () => ({
  useDepartments: () => ({ data: [{ id: "d1", name: "MSA-Teachers" }] }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

import { StaffDayRegister } from "@/app/(dashboard)/attendance/_components/staff-day-register";

beforeEach(() => {
  manualMark.mockClear();
});

describe("StaffDayRegister", () => {
  it("tags a manual entry with the author and leaves biometric untagged", () => {
    render(<StaffDayRegister branchId="br1" canMark={false} />);
    const manualRow = screen.getByText("Rahul Pawar").closest("tr")!;
    expect(within(manualRow).getByText("Manual")).toBeInTheDocument();
    expect(within(manualRow).getByText(/by Admin User \(Super Admin\)/)).toBeInTheDocument();

    const bioRow = screen.getByText("Sneha Rao").closest("tr")!;
    expect(within(bioRow).queryByText("Manual")).not.toBeInTheDocument();
  });

  it("hides the Action column when the user cannot mark", () => {
    render(<StaffDayRegister branchId="br1" canMark={false} />);
    expect(screen.queryByRole("columnheader", { name: "Action" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^(mark|edit)$/i })).not.toBeInTheDocument();
  });

  it("offers Mark for an empty row and Edit for an existing entry when allowed", () => {
    render(<StaffDayRegister branchId="br1" canMark />);
    expect(screen.getByRole("columnheader", { name: "Action" })).toBeInTheDocument();
    const emptyRow = screen.getByText("Vivek Jain").closest("tr")!;
    expect(within(emptyRow).getByRole("button", { name: /^mark$/i })).toBeInTheDocument();
    const filledRow = screen.getByText("Rahul Pawar").closest("tr")!;
    expect(within(filledRow).getByRole("button", { name: /^edit$/i })).toBeInTheDocument();
  });

  it("opens the manual-mark dialog from the Mark button", async () => {
    const user = userEvent.setup();
    render(<StaffDayRegister branchId="br1" canMark />);
    const emptyRow = screen.getByText("Vivek Jain").closest("tr")!;
    await user.click(within(emptyRow).getByRole("button", { name: /^mark$/i }));
    expect(
      await screen.findByText(/mark attendance manually/i),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("In Time")).toBeInTheDocument();
    expect(screen.getByLabelText(/Out Time/)).toBeInTheDocument();
  });
});
