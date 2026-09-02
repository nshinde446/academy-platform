import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type {
  RankList as RankListData,
  TestSummary,
} from "@/app/(dashboard)/test-portal/_schemas/test-portal";

const RANKLIST: RankListData = {
  test_id: "t1",
  test_name: "11th CET PCM",
  total_marks: 200,
  ranked: [
    { rank: 1, student_id: "s1", prn: "PRNA", name: "Aarohi A", marks_obtained: 186, percentage: 93, absent: false },
    { rank: 2, student_id: "s2", prn: "PRNB", name: "Bhavna B", marks_obtained: 180, percentage: 90, absent: false },
  ],
  absentees: [
    { rank: null, student_id: "s4", prn: "PRND", name: "Deepak D", marks_obtained: null, percentage: null, absent: true },
  ],
  needs_review: [{ id: "r1", csv_prn: "PRNX", csv_name: "Ghost", resolved: false }],
};

const uploadMutate = vi.fn().mockResolvedValue({ matched: 2, absent: 1, needs_review: 1, total_rows: 3 });
const downloadMutate = vi.fn();

vi.mock("@/app/(dashboard)/test-portal/_hooks/use-test-portal", () => ({
  useRankList: () => ({ data: RANKLIST, isLoading: false, isError: false }),
  useUploadResult: () => ({ mutateAsync: uploadMutate, isPending: false }),
  useDownloadRankList: () => ({ mutate: downloadMutate, isPending: false }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

import { RankList } from "@/app/(dashboard)/test-portal/_components/rank-list";

const TEST: TestSummary = {
  id: "t1",
  name: "11th CET PCM",
  batch_id: "b1",
  subject_id: "sub1",
  subject_ids: ["sub1"],
  scheduled_at: "2026-08-31T00:00:00Z",
  total_marks: 200,
  omr_type: "100Q",
  test_status: "SCHEDULED",
};

beforeEach(() => {
  uploadMutate.mockClear();
  downloadMutate.mockClear();
});

describe("Test Portal RankList", () => {
  it("renders ranked students highest-first with the absentee at the bottom", () => {
    render(<RankList branchId="br1" test={TEST} />);
    const table = screen.getByRole("table");
    const rows = within(table).getAllByRole("row").slice(1); // drop header
    // Row order: rank 1, rank 2, then the absentee.
    expect(within(rows[0]).getByText("Aarohi A")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Bhavna B")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Deepak D")).toBeInTheDocument();
    expect(within(rows[2]).getByText("ABSENT")).toBeInTheDocument();
  });

  it("surfaces the needs-review count", () => {
    render(<RankList branchId="br1" test={TEST} />);
    expect(screen.getByText(/1 row need review/i)).toBeInTheDocument();
  });

  it("downloads the rank list as PDF and Excel", async () => {
    const user = userEvent.setup();
    render(<RankList branchId="br1" test={TEST} />);
    await user.click(screen.getByRole("button", { name: /download pdf/i }));
    await user.click(screen.getByRole("button", { name: /download excel/i }));
    expect(downloadMutate).toHaveBeenNthCalledWith(1, { testId: "t1", format: "pdf" });
    expect(downloadMutate).toHaveBeenNthCalledWith(2, { testId: "t1", format: "xlsx" });
  });
});
