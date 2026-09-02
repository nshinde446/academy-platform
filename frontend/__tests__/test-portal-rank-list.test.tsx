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
const uploadKeyMutate = vi.fn().mockResolvedValue({ answer_key_file: "k", filename: "key.pdf" });
const downloadKeyMutate = vi.fn();

vi.mock("@/app/(dashboard)/test-portal/_hooks/use-test-portal", () => ({
  useRankList: () => ({ data: RANKLIST, isLoading: false, isError: false }),
  useUploadResult: () => ({ mutateAsync: uploadMutate, isPending: false }),
  useDownloadRankList: () => ({ mutate: downloadMutate, isPending: false }),
  useUploadAnswerKey: () => ({ mutateAsync: uploadKeyMutate, isPending: false }),
  useDownloadAnswerKey: () => ({ mutate: downloadKeyMutate, isPending: false }),
  useResolveReview: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

// The resolve dialog is unit-tested on its own; stub it here so RankList renders
// without a QueryClientProvider (the real dialog fetches the student roster).
vi.mock(
  "@/app/(dashboard)/test-portal/_components/resolve-review-dialog",
  () => ({
    ResolveReviewDialog: ({ open }: { open: boolean }) =>
      open ? <div data-testid="resolve-dialog" /> : null,
  }),
);

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
  answer_key_file: null,
  test_status: "SCHEDULED",
};

beforeEach(() => {
  uploadMutate.mockClear();
  downloadMutate.mockClear();
  uploadKeyMutate.mockClear();
  downloadKeyMutate.mockClear();
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

  it("offers a downloadable sample ZipGrade CSV for reference", () => {
    render(<RankList branchId="br1" test={TEST} />);
    const link = screen.getByRole("link", { name: /sample csv/i });
    expect(link).toHaveAttribute("href", "/zipgrade-sample.csv");
    expect(link).toHaveAttribute("download");
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

  it("lists each needs-review row and opens the resolve dialog", async () => {
    const user = userEvent.setup();
    render(<RankList branchId="br1" test={TEST} />);
    // The one unmatched row (PRNX / Ghost) is listed with a Resolve button.
    expect(screen.getByText("PRNX")).toBeInTheDocument();
    expect(screen.queryByTestId("resolve-dialog")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /resolve/i }));
    expect(screen.getByTestId("resolve-dialog")).toBeInTheDocument();
  });

  it("shows an upload-answer-key button, and a download only once a key exists", async () => {
    const { rerender } = render(<RankList branchId="br1" test={TEST} />);
    // No key yet → upload label, no download button.
    expect(screen.getByRole("button", { name: /upload answer key/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^answer key$/i })).not.toBeInTheDocument();

    // Once a key is stored → label flips to Replace and a download appears.
    rerender(<RankList branchId="br1" test={{ ...TEST, answer_key_file: "answer-keys/t1--key.pdf" }} />);
    expect(screen.getByRole("button", { name: /replace answer key/i })).toBeInTheDocument();
    const dl = screen.getByRole("button", { name: /^answer key$/i });
    await userEvent.setup().click(dl);
    expect(downloadKeyMutate).toHaveBeenCalledWith({ testId: "t1" });
  });
});
