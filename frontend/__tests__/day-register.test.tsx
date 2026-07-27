import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ClassroomRegisterRow } from "@/app/(dashboard)/attendance/_schemas/attendance";

const ROWS: ClassroomRegisterRow[] = [
  {
    student_id: "s1", name: "Aarav Patil", enrollment_number: "EN-1",
    parent_mobile: "9000000001", mark: "P", day_status: "PRESENT",
    first_in: "2026-06-22T03:59:00Z", last_out: null, signoff: "MISSING",
  },
  {
    student_id: "s2", name: "Diya Shah", enrollment_number: "EN-2",
    parent_mobile: null, mark: "A", day_status: "ABSENT",
    first_in: null, last_out: null, signoff: "NA",
  },
];

const downloadMutate = vi.fn();

// Mock the data hooks so the component renders without a network.
vi.mock("@/app/(dashboard)/attendance/_hooks/use-attendance", () => ({
  useClassroomRegister: () => ({ data: ROWS, isLoading: false, isError: false }),
  useDownloadAttendanceReport: () => ({ mutate: downloadMutate, isPending: false }),
}));

import { DayRegister } from "@/app/(dashboard)/attendance/_components/day-register";

const BATCHES = [{ id: "b1", name: "Batch A" }];

describe("DayRegister", () => {
  it("prompts to pick a batch before showing the register", () => {
    render(<DayRegister branchId="br1" batches={BATCHES} />);
    expect(
      screen.getByText(/pick a batch and day/i),
    ).toBeInTheDocument();
    // No register table until a batch is chosen (names may appear in the
    // report student dropdown, so assert on the table, not the name).
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("renders the P/A register once a batch is selected", async () => {
    const user = userEvent.setup();
    render(<DayRegister branchId="br1" batches={BATCHES} />);
    await user.selectOptions(screen.getByLabelText("Select batch"), "b1");

    // Names appear in both the report dropdown and the table — scope to table.
    const table = screen.getByRole("table");
    expect(within(table).getByText("Aarav Patil")).toBeInTheDocument();
    expect(within(table).getByText("Diya Shah")).toBeInTheDocument();
    expect(within(table).getByText("Present")).toBeInTheDocument();
    expect(within(table).getByText("Absent")).toBeInTheDocument();
  });

  it("summarises present count and missed punch-outs", async () => {
    const user = userEvent.setup();
    render(<DayRegister branchId="br1" batches={BATCHES} />);
    await user.selectOptions(screen.getByLabelText("Select batch"), "b1");

    // 1 of 2 present -> 50%; one MISSING sign-off.
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("1/2")).toBeInTheDocument();
  });

  it("downloads an all-batches report without needing a batch", async () => {
    const user = userEvent.setup();
    downloadMutate.mockClear();
    render(<DayRegister branchId="br1" batches={BATCHES} />);

    // "All batches" group is always enabled; click its Excel button.
    const group = screen.getByText("All batches").parentElement!;
    await user.click(within(group).getByText("Excel"));

    expect(downloadMutate).toHaveBeenCalledTimes(1);
    expect(downloadMutate.mock.calls[0][0]).toMatchObject({
      scope: "all-batches",
      fmt: "xlsx",
    });
  });

  it("filters the visible roster to the selected student", async () => {
    const user = userEvent.setup();
    render(<DayRegister branchId="br1" batches={BATCHES} />);
    await user.selectOptions(screen.getByLabelText("Select batch"), "b1");

    // Whole batch first.
    let table = screen.getByRole("table");
    expect(within(table).getByText("Aarav Patil")).toBeInTheDocument();
    expect(within(table).getByText("Diya Shah")).toBeInTheDocument();

    // Pick a student -> table narrows to just them.
    await user.selectOptions(screen.getByLabelText("Student"), "s1");
    table = screen.getByRole("table");
    expect(within(table).getByText("Aarav Patil")).toBeInTheDocument();
    expect(within(table).queryByText("Diya Shah")).not.toBeInTheDocument();
  });

  it("scopes the main download to batch when unfiltered, student when filtered", async () => {
    const user = userEvent.setup();
    downloadMutate.mockClear();
    render(<DayRegister branchId="br1" batches={BATCHES} />);
    await user.selectOptions(screen.getByLabelText("Select batch"), "b1");

    // No student selected -> "This batch".
    let group = screen.getByText("This batch").parentElement!;
    await user.click(within(group).getByText("PDF"));
    expect(downloadMutate.mock.calls.at(-1)![0]).toMatchObject({
      scope: "batch",
      id: "b1",
      fmt: "pdf",
    });

    // Select a student -> the same primary group emits an individual report.
    await user.selectOptions(screen.getByLabelText("Student"), "s1");
    group = screen.getByText("Selected student").parentElement!;
    await user.click(within(group).getByText("Excel"));
    expect(downloadMutate.mock.calls.at(-1)![0]).toMatchObject({
      scope: "student",
      id: "s1",
      fmt: "xlsx",
    });
  });
});
