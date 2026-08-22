import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ClassroomRegisterRow } from "@/app/(dashboard)/attendance/_schemas/attendance";

const ROWS: ClassroomRegisterRow[] = [
  {
    student_id: "s1", name: "Aarav Patil", enrollment_number: "EN-1",
    rfid_number: "6433012", parent_mobile: "9000000001", mark: "P",
    day_status: "PRESENT", first_in: "2026-06-22T03:59:00Z", last_out: null,
    signoff: "MISSING", source: "BIOMETRIC",
  },
  {
    student_id: "s2", name: "Diya Shah", enrollment_number: "EN-2",
    rfid_number: null, parent_mobile: null, mark: "A", day_status: "ABSENT",
    first_in: null, last_out: null, signoff: "NA", source: "SYSTEM",
  },
  {
    student_id: "s3", name: "Manual Mia", enrollment_number: "EN-3",
    rfid_number: null, parent_mobile: "9000000003", mark: "P",
    day_status: "PRESENT", first_in: null, last_out: null, signoff: "NA",
    source: "MANUAL",
  },
];

const downloadMutate = vi.fn();
const manualMark = vi.fn().mockResolvedValue({});
const notifyMutate = vi.fn().mockResolvedValue({ queued: 1 });

vi.mock("@/app/(dashboard)/attendance/_hooks/use-attendance", () => ({
  useClassroomRegister: () => ({ data: ROWS, isLoading: false, isError: false }),
  useDownloadAttendanceReport: () => ({ mutate: downloadMutate, isPending: false }),
  useManualMarkDay: () => ({ mutateAsync: manualMark, isPending: false }),
  useSendDayNotification: () => ({ mutateAsync: notifyMutate, isPending: false }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

import { DayRegister } from "@/app/(dashboard)/attendance/_components/day-register";

const BATCHES = [{ id: "b1", name: "Batch A" }];

async function selectBatch(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(screen.getByLabelText("Select batch"), "b1");
}

beforeEach(() => {
  downloadMutate.mockClear();
  manualMark.mockClear();
  notifyMutate.mockClear();
});

describe("DayRegister", () => {
  it("prompts to pick a batch before showing the register", () => {
    render(<DayRegister branchId="br1" batches={BATCHES} isSuperAdmin={false} />);
    expect(screen.getByText(/pick a batch and day/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("renders a PRN column with the enrollment number", async () => {
    const user = userEvent.setup();
    render(<DayRegister branchId="br1" batches={BATCHES} isSuperAdmin={false} />);
    await selectBatch(user);

    const table = screen.getByRole("table");
    expect(within(table).getByText("PRN")).toBeInTheDocument();
    expect(within(table).getByText("EN-1")).toBeInTheDocument();
  });

  it("filters the roster to Absent, then Present", async () => {
    const user = userEvent.setup();
    render(<DayRegister branchId="br1" batches={BATCHES} isSuperAdmin={false} />);
    await selectBatch(user);

    await user.click(screen.getByRole("radio", { name: "Absent" }));
    let table = screen.getByRole("table");
    expect(within(table).getByText("Diya Shah")).toBeInTheDocument();
    expect(within(table).queryByText("Aarav Patil")).not.toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Present" }));
    table = screen.getByRole("table");
    expect(within(table).getByText("Aarav Patil")).toBeInTheDocument();
    expect(within(table).queryByText("Diya Shah")).not.toBeInTheDocument();
  });

  it("shows a 'Manually Marked' tag for hand-marked rows", async () => {
    const user = userEvent.setup();
    render(<DayRegister branchId="br1" batches={BATCHES} isSuperAdmin={false} />);
    await selectBatch(user);
    expect(screen.getByText(/manually marked/i)).toBeInTheDocument();
  });

  it("hides the manual-mark action from non-super-admins", async () => {
    const user = userEvent.setup();
    render(<DayRegister branchId="br1" batches={BATCHES} isSuperAdmin={false} />);
    await selectBatch(user);
    expect(screen.queryByRole("button", { name: /mark present/i })).not.toBeInTheDocument();
  });

  it("lets a super-admin mark an absent student present", async () => {
    const user = userEvent.setup();
    render(<DayRegister branchId="br1" batches={BATCHES} isSuperAdmin />);
    await selectBatch(user);

    // Only the absent student (Diya) gets the row action.
    await user.click(screen.getByRole("button", { name: /mark present/i }));
    // The dialog adds a second "Mark present" (its confirm) — click the last.
    const buttons = screen.getAllByRole("button", { name: /mark present/i });
    await user.click(buttons[buttons.length - 1]);
    expect(manualMark).toHaveBeenCalledWith({ student_id: "s2", status: "PRESENT" });
  });

  it("queues notifications for selected students", async () => {
    const user = userEvent.setup();
    render(<DayRegister branchId="br1" batches={BATCHES} isSuperAdmin={false} />);
    await selectBatch(user);

    await user.click(screen.getByLabelText("Select Aarav Patil"));
    await user.click(screen.getByRole("button", { name: /send whatsapp notification/i }));
    expect(notifyMutate).toHaveBeenCalledTimes(1);
    expect(notifyMutate.mock.calls[0][0]).toMatchObject({
      batch_id: "b1",
      student_ids: ["s1"],
    });
  });

  it("downloads the single-day report with the day scope", async () => {
    const user = userEvent.setup();
    render(<DayRegister branchId="br1" batches={BATCHES} isSuperAdmin={false} />);
    await selectBatch(user);

    // Match the download-group label ("Day report (YYYY-MM-DD)"), not the
    // descriptive paragraph that also mentions the day report.
    const group = screen.getByText(/day report \(/i).parentElement!;
    await user.click(within(group).getByText("PDF"));
    expect(downloadMutate.mock.calls.at(-1)![0]).toMatchObject({
      scope: "day",
      id: "b1",
      fmt: "pdf",
    });
  });

  it("downloads an all-batches report without needing a batch", async () => {
    const user = userEvent.setup();
    render(<DayRegister branchId="br1" batches={BATCHES} isSuperAdmin={false} />);

    const group = screen.getByText("All batches").parentElement!;
    await user.click(within(group).getByText("Excel"));
    expect(downloadMutate).toHaveBeenCalledTimes(1);
    expect(downloadMutate.mock.calls[0][0]).toMatchObject({
      scope: "all-batches",
      fmt: "xlsx",
    });
  });
});
