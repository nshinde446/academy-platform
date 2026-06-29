import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const syncMutate = vi.fn().mockResolvedValue([{ id: "r1" }, { id: "r2" }]);
const markMutate = vi.fn().mockResolvedValue({});

const LECTURE = {
  id: "lec1",
  batch_id: "b1",
  scheduled_start: "2026-06-22T04:30:00Z",
  scheduled_end: "2026-06-22T05:30:00Z",
  lecture_status: "completed",
};

vi.mock("@/store/user-store", () => ({
  useUserStore: (sel: (s: unknown) => unknown) =>
    sel({
      user: {
        branch_roles: [
          { branch_id: "br1", branch_name: "Pune Campus", branch_code: "PUN" },
        ],
      },
    }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

vi.mock("@/app/(dashboard)/lectures/_hooks/use-lectures", () => ({
  useLectures: () => ({ data: [LECTURE], isLoading: false, isError: false }),
  useBatchesForLectures: () => ({ data: [{ id: "b1", name: "NEET-12" }] }),
}));

vi.mock("@/app/(dashboard)/students/_hooks/use-students", () => ({
  useStudentsWithStats: () => ({
    data: [
      { id: "s1", batch_id: "b1", first_name: "Aarav", last_name: "Patil",
        enrollment_number: "EN1" },
    ],
  }),
  studentKeys: { withStats: (b: string) => ["students", "withStats", b] },
}));

vi.mock("@/app/(dashboard)/attendance/_hooks/use-attendance", () => ({
  useLectureAttendance: () => ({ data: [] }),
  useMarkAttendance: () => ({ mutateAsync: markMutate, isPending: false }),
  useSyncAttendanceSource: () => ({ mutateAsync: syncMutate, isPending: false }),
}));

import AttendancePage from "@/app/(dashboard)/attendance/page";

describe("Attendance source buttons", () => {
  beforeEach(() => {
    syncMutate.mockClear();
  });

  it("shows the branch name and both source buttons", () => {
    render(<AttendancePage />);
    expect(screen.getByText("Pune Campus")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "eTimeOffice" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "BioMax" })).toBeInTheDocument();
    // The old single button is gone.
    expect(
      screen.queryByRole("button", { name: /process biometric punches/i }),
    ).not.toBeInTheDocument();
  });

  it("pulls from eTimeOffice after confirming", async () => {
    const user = userEvent.setup();
    render(<AttendancePage />);

    await user.click(screen.getByRole("button", { name: "eTimeOffice" }));
    expect(
      await screen.findByText(/Pull from eTimeOffice\?/i),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /pull & apply/i }));

    await waitFor(() => expect(syncMutate).toHaveBeenCalledTimes(1));
    expect(syncMutate.mock.calls[0][0]).toMatchObject({ source: "etimeoffice" });
  });

  it("processes BioMax after confirming", async () => {
    const user = userEvent.setup();
    render(<AttendancePage />);

    await user.click(screen.getByRole("button", { name: "BioMax" }));
    expect(
      await screen.findByText(/Process BioMax punches\?/i),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^process$/i }));

    await waitFor(() => expect(syncMutate).toHaveBeenCalledTimes(1));
    expect(syncMutate.mock.calls[0][0]).toMatchObject({ source: "biomax" });
  });
});
