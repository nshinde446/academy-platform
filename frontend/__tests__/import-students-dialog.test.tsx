import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ImportStudentsDialog } from "@/app/(dashboard)/students/_components/import-students-dialog";
import apiClient from "@/services/api-client";

vi.mock("@/services/api-client", () => ({
  default: { post: vi.fn() },
}));

function renderDialog() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ImportStudentsDialog branchId="b1" />
    </QueryClientProvider>,
  );
}

describe("ImportStudentsDialog", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // Clears the mockResolvedValueOnce queue between tests (restoreAllMocks
    // doesn't reset manually-created vi.fn() mocks).
    (apiClient.post as ReturnType<typeof vi.fn>).mockReset();
  });

  it("offers a Download sample CSV button inside the dialog", async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.click(screen.getByRole("button", { name: /import students/i }));
    expect(
      screen.getByRole("button", { name: /download sample csv/i }),
    ).toBeInTheDocument();
  });

  it("downloads a template with per-row Class / Target / Batch columns", async () => {
    const user = userEvent.setup();
    let captured: Blob | null = null;
    URL.createObjectURL = ((b: Blob) => {
      captured = b;
      return "blob:mock";
    }) as typeof URL.createObjectURL;
    URL.revokeObjectURL = (() => {}) as typeof URL.revokeObjectURL;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => {},
    );

    renderDialog();
    await user.click(screen.getByRole("button", { name: /import students/i }));
    await user.click(
      screen.getByRole("button", { name: /download sample csv/i }),
    );

    expect(captured).toBeTruthy();
    const text = await (captured as unknown as Blob).text();
    // Required + optional INPUT headers.
    expect(text).toContain("Name");
    expect(text).toContain("Class");
    expect(text).toContain("Target");
    expect(text).toContain("Batch");
    expect(text).toContain("Roll No");
    expect(text).toContain("Parent Mobile");
    expect(text).toContain("RFIDNumber");
    // Sample rows exercise common class / exam / batch values.
    expect(text).toMatch(/NEET/);
    expect(text).toMatch(/JEE-Main/);
    // Derived columns must not leak into the template.
    expect(text).not.toMatch(/\bRank\b/);
    expect(text).not.toMatch(/Avg score/i);
    expect(text).not.toMatch(/Attendance/);
    expect(text).not.toMatch(/\bDPP\b/);
    expect(text).not.toMatch(/Fees/);
  });

  it("sample template exercises every allowed Class and Target value", async () => {
    const user = userEvent.setup();
    let captured: Blob | null = null;
    URL.createObjectURL = ((b: Blob) => {
      captured = b;
      return "blob:mock";
    }) as typeof URL.createObjectURL;
    URL.revokeObjectURL = (() => {}) as typeof URL.revokeObjectURL;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => {},
    );

    renderDialog();
    await user.click(screen.getByRole("button", { name: /import students/i }));
    await user.click(
      screen.getByRole("button", { name: /download sample csv/i }),
    );

    const text = await (captured as unknown as Blob).text();
    // Allowed Class values.
    for (const cls of ["9", "10", "11", "12", "Dropper"]) {
      expect(text).toContain(`,${cls},`);
    }
    // Allowed Target values.
    for (const t of [
      "NEET",
      "JEE-Main",
      "JEE-Advanced",
      "MHT-CET",
      "Both",
      "Foundation",
      "Other",
    ]) {
      expect(text).toContain(`,${t},`);
    }
  });

  it("previews the batch split, then offers to create missing batches", async () => {
    const user = userEvent.setup();
    const post = apiClient.post as ReturnType<typeof vi.fn>;
    // 1st call = preview, 2nd = import.
    post.mockResolvedValueOnce({
      data: {
        total_rows: 2,
        importable_rows: 2,
        rows_missing_name: 0,
        rows_invalid_enrolment: 0,
        unbatched_rows: 0,
        existing_batches: 0,
        missing_batches: 1,
        blocked_batches: 0,
        batches: [
          {
            code: "NEET-11-A",
            student_count: 2,
            exists: false,
            target: "NEET",
            suggested_course_code: "NEET",
            suggested_course_name: "NEET Preparation",
            suggested_exam_date: "2026-05-04",
            creatable: true,
            blocker: null,
          },
        ],
        row_issues: [],
      },
    });
    post.mockResolvedValueOnce({
      data: {
        imported: 2,
        skipped: 0,
        errors: [],
        batches_created: ["NEET-11-A"],
      },
    });

    renderDialog();
    await user.click(screen.getByRole("button", { name: /import students/i }));

    const fileInput = screen.getByLabelText(/file/i) as HTMLInputElement;
    const file = new File(["Name\nfoo"], "x.csv", { type: "text/csv" });
    await user.upload(fileInput, file);
    await user.click(screen.getByRole("button", { name: /preview import/i }));

    // Preview surfaces the missing batch + a create-missing checkbox (on).
    await waitFor(() => {
      expect(screen.getByText("NEET-11-A")).toBeInTheDocument();
    });
    expect(screen.getByText(/1 missing/i)).toBeInTheDocument();
    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    expect(checkbox.checked).toBe(true);

    await user.click(screen.getByRole("button", { name: /^import$/i }));

    await waitFor(() => {
      expect(screen.getByText(/Created 1 batch/i)).toBeInTheDocument();
    });
    // The import call asked the server to create the missing batches.
    expect(post).toHaveBeenLastCalledWith(
      "/api/v1/students/import",
      expect.any(FormData),
      expect.objectContaining({
        params: { branch_id: "b1", create_missing_batches: true },
      }),
    );
  });

  it("flags batches that can't be auto-created in the preview", async () => {
    const user = userEvent.setup();
    const post = apiClient.post as ReturnType<typeof vi.fn>;
    post.mockResolvedValueOnce({
      data: {
        total_rows: 1,
        importable_rows: 1,
        rows_missing_name: 0,
        rows_invalid_enrolment: 0,
        unbatched_rows: 0,
        existing_batches: 0,
        missing_batches: 1,
        blocked_batches: 1,
        batches: [
          {
            code: "NEET-11-X",
            student_count: 1,
            exists: false,
            target: "NEET",
            suggested_course_code: "NEET",
            suggested_course_name: "NEET Preparation",
            suggested_exam_date: null,
            creatable: false,
            blocker: "needs an academic year starting at 2026 (create it first)",
          },
        ],
        row_issues: [],
      },
    });

    renderDialog();
    await user.click(screen.getByRole("button", { name: /import students/i }));

    const fileInput = screen.getByLabelText(/file/i) as HTMLInputElement;
    const file = new File(["Name\nfoo"], "x.csv", { type: "text/csv" });
    await user.upload(fileInput, file);
    await user.click(screen.getByRole("button", { name: /preview import/i }));

    // The row shows WHY it can't be created, and a warning is surfaced.
    expect(await screen.findByText(/can't create —/i)).toBeInTheDocument();
    expect(
      screen.getByText(/academic year starting at 2026/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/1 batch\(es\) can't be\s+auto-created/i),
    ).toBeInTheDocument();
  });

  it("shows partial-failure feedback when the server skips rows", async () => {
    const user = userEvent.setup();
    const post = apiClient.post as ReturnType<typeof vi.fn>;
    post.mockResolvedValueOnce({
      data: {
        total_rows: 2,
        importable_rows: 1,
        rows_missing_name: 0,
        rows_invalid_enrolment: 1,
        unbatched_rows: 0,
        existing_batches: 0,
        missing_batches: 1,
        blocked_batches: 0,
        batches: [
          {
            code: "MHT-11-A",
            student_count: 1,
            exists: false,
            target: "MHT-CET",
            suggested_course_code: "MHT-CET",
            suggested_course_name: "MHT-CET Preparation",
            suggested_exam_date: "2026-04-24",
            creatable: true,
            blocker: null,
          },
        ],
        row_issues: ["Row 2: Invalid target_exam 'JEE'."],
      },
    });
    post.mockResolvedValueOnce({
      data: {
        imported: 0,
        skipped: 2,
        errors: [
          "Row 2: Invalid target_exam 'JEE'.",
          "Row 3: unknown batch code 'MHT-11-A'",
        ],
        batches_created: [],
      },
    });

    renderDialog();
    await user.click(screen.getByRole("button", { name: /import students/i }));

    const fileInput = screen.getByLabelText(/file/i) as HTMLInputElement;
    const file = new File(["Name\nfoo"], "x.csv", { type: "text/csv" });
    await user.upload(fileInput, file);
    await user.click(screen.getByRole("button", { name: /preview import/i }));

    await user.click(await screen.findByRole("button", { name: /^import$/i }));

    await waitFor(() => {
      expect(screen.getByText(/no rows were saved/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Invalid target_exam 'JEE'/)).toBeInTheDocument();
    expect(screen.getByText(/unknown batch code/i)).toBeInTheDocument();
    // Import button is replaced by a Close / Upload another file pair.
    expect(screen.queryByRole("button", { name: /^import$/i })).toBeNull();
  });
});
