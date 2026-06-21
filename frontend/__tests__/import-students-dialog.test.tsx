import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ImportStudentsDialog } from "@/app/(dashboard)/students/_components/import-students-dialog";
import apiClient from "@/services/api-client";

vi.mock("@/services/api-client", () => ({
  default: { post: vi.fn(), get: vi.fn() },
}));

// A completed import job (the dialog polls GET /import/jobs/{id}).
function completedJob(overrides: Record<string, unknown> = {}) {
  return {
    data: {
      id: "job-1",
      job_status: "completed",
      filename: "x.csv",
      total_rows: 2,
      processed_rows: 2,
      imported: 2,
      skipped: 0,
      subjects_created: 0,
      errors: [],
      warnings: [],
      batches_created: [],
      academic_years_created: [],
      error_detail: null,
      import_id: "job-1",
      ...overrides,
    },
  };
}

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
    (apiClient.get as ReturnType<typeof vi.fn>).mockReset();
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
    // Optional batch-creation override columns (design §5).
    expect(text).toContain("Course_opt");
    expect(text).toContain("Duration");
    expect(text).toContain("Academic_year");
    expect(text).toContain("Syllabus");
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
        duplicate_rows: 0,
        unbatched_rows: 0,
        existing_batches: 0,
        missing_batches: 1,
        blocked_batches: 0,
        blocking_error: null,
        new_academic_years: [],
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
    // 2nd post = start the background job.
    post.mockResolvedValueOnce({
      data: { id: "job-1", job_status: "processing", total_rows: 2 },
    });
    // Polled job status — completed with the result.
    (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      completedJob({ batches_created: ["NEET-11-A"], subjects_created: 4 }),
    );

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

    // The job is started, then polled to completion → result shown.
    await waitFor(() => {
      expect(screen.getByText(/Created 1 batch/i)).toBeInTheDocument();
    });
    expect(post).toHaveBeenCalledWith(
      "/api/v1/students/import/start",
      expect.any(FormData),
      expect.objectContaining({
        params: { branch_id: "b1", create_missing_batches: true },
      }),
    );
  });

  it("offers to undo a successful import and reports what was removed", async () => {
    const user = userEvent.setup();
    const post = apiClient.post as ReturnType<typeof vi.fn>;
    // preview -> import -> undo.
    post.mockResolvedValueOnce({
      data: {
        total_rows: 2,
        importable_rows: 2,
        rows_missing_name: 0,
        rows_invalid_enrolment: 0,
        duplicate_rows: 0,
        unbatched_rows: 0,
        existing_batches: 1,
        missing_batches: 0,
        blocked_batches: 0,
        blocking_error: null,
        new_academic_years: [],
        batches: [
          {
            code: "BATCH-A",
            student_count: 2,
            exists: true,
            target: "NEET",
            suggested_course_code: null,
            suggested_course_name: null,
            suggested_exam_date: null,
            creatable: true,
            blocker: null,
          },
        ],
        row_issues: [],
      },
    });
    // start job, then undo.
    post.mockResolvedValueOnce({
      data: { id: "job-42", job_status: "processing", total_rows: 2 },
    });
    post.mockResolvedValueOnce({
      data: { students_deleted: 2, batches_deleted: 0, subjects_deleted: 0 },
    });
    (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      completedJob({ id: "job-42", import_id: "job-42", batches_created: [] }),
    );

    renderDialog();
    await user.click(screen.getByRole("button", { name: /import students/i }));
    const fileInput = screen.getByLabelText(/file/i) as HTMLInputElement;
    await user.upload(
      fileInput,
      new File(["Name\nfoo"], "x.csv", { type: "text/csv" }),
    );
    await user.click(screen.getByRole("button", { name: /preview import/i }));
    await user.click(await screen.findByRole("button", { name: /^import$/i }));

    // After a clean import, an Undo action is offered.
    const undoBtn = await screen.findByRole("button", { name: /undo import/i });
    await user.click(undoBtn);

    await waitFor(() => {
      expect(screen.getByText(/undone — removed 2 student/i)).toBeInTheDocument();
    });
    expect(post).toHaveBeenLastCalledWith(
      "/api/v1/students/import/job-42/undo",
      null,
      expect.objectContaining({ params: { branch_id: "b1" } }),
    );
    // Undo is offered only once — it disappears after running.
    expect(
      screen.queryByRole("button", { name: /undo import/i }),
    ).toBeNull();
  });

  it("surfaces §3 warnings on an otherwise successful import", async () => {
    const user = userEvent.setup();
    const post = apiClient.post as ReturnType<typeof vi.fn>;
    post.mockResolvedValueOnce({
      data: {
        total_rows: 1,
        importable_rows: 1,
        rows_missing_name: 0,
        rows_invalid_enrolment: 0,
        rows_invalid_consistency: 0,
        rows_with_warnings: 1,
        duplicate_rows: 0,
        unbatched_rows: 0,
        existing_batches: 1,
        missing_batches: 0,
        blocked_batches: 0,
        blocking_error: null,
        new_academic_years: [],
        batches: [
          {
            code: "BATCH-A",
            student_count: 1,
            exists: true,
            target: "NEET",
            suggested_course_code: null,
            suggested_course_name: null,
            suggested_exam_date: null,
            creatable: true,
            blocker: null,
          },
        ],
        row_issues: [
          "Row 2: warning — Class 9 targeting NEET — Foundation remap not yet supported, enrolling as-is",
        ],
      },
    });
    post.mockResolvedValueOnce({
      data: { id: "job-w", job_status: "processing", total_rows: 1 },
    });
    (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      completedJob({
        id: "job-w",
        import_id: "job-w",
        total_rows: 1,
        processed_rows: 1,
        imported: 1,
        warnings: [
          "Row 2: Class 9 targeting NEET — Foundation remap not yet supported, enrolling as-is",
        ],
      }),
    );

    renderDialog();
    await user.click(screen.getByRole("button", { name: /import students/i }));
    await user.upload(
      screen.getByLabelText(/file/i) as HTMLInputElement,
      new File(["Name\nfoo"], "x.csv", { type: "text/csv" }),
    );
    await user.click(screen.getByRole("button", { name: /preview import/i }));
    // Preview already calls out the warning row.
    expect(
      await screen.findByText(/1 row\(s\) have warnings/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^import$/i }));
    await waitFor(() => {
      expect(
        screen.getByText(/imported with 1 warning/i),
      ).toBeInTheDocument();
    });
    expect(
      screen.getAllByText(/Class 9 targeting NEET/i).length,
    ).toBeGreaterThan(0);
  });

  it("shows the academic years it will auto-create in the preview", async () => {
    const user = userEvent.setup();
    const post = apiClient.post as ReturnType<typeof vi.fn>;
    post.mockResolvedValueOnce({
      data: {
        total_rows: 1,
        importable_rows: 1,
        rows_missing_name: 0,
        rows_invalid_enrolment: 0,
        rows_invalid_consistency: 0,
        rows_with_warnings: 0,
        duplicate_rows: 0,
        unbatched_rows: 0,
        existing_batches: 1,
        missing_batches: 0,
        blocked_batches: 0,
        blocking_error: null,
        new_academic_years: ["2026-27", "2027-28"],
        batches: [],
        row_issues: [],
      },
    });

    renderDialog();
    await user.click(screen.getByRole("button", { name: /import students/i }));
    await user.upload(
      screen.getByLabelText(/file/i) as HTMLInputElement,
      new File(["Name\nfoo"], "x.csv", { type: "text/csv" }),
    );
    await user.click(screen.getByRole("button", { name: /preview import/i }));

    expect(
      await screen.findByText(/Will create academic year\(s\):/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/2026-27, 2027-28/)).toBeInTheDocument();
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
        duplicate_rows: 0,
        unbatched_rows: 0,
        existing_batches: 0,
        missing_batches: 1,
        blocked_batches: 1,
        blocking_error: null,
        new_academic_years: [],
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
        blocking_error: null,
        new_academic_years: [],
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
      data: { id: "job-pf", job_status: "processing", total_rows: 2 },
    });
    (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue(
      completedJob({
        id: "job-pf",
        import_id: null,
        total_rows: 2,
        processed_rows: 2,
        imported: 0,
        skipped: 2,
        errors: [
          "Row 2: Invalid target_exam 'JEE'.",
          "Row 3: unknown batch code 'MHT-11-A'",
        ],
      }),
    );

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
