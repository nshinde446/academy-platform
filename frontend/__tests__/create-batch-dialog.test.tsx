import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import type { ReactNode } from "react";
import { CreateBatchDialog } from "@/app/(dashboard)/batches/_components/create-batch-dialog";
import type {
  AcademicYearResponse,
  CourseResponse,
} from "@/app/(dashboard)/batches/_schemas/batch";

function withQuery(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

const MOCK_YEARS: AcademicYearResponse[] = [
  {
    id: "ay1",
    branch_id: "br1",
    name: "2025-2026",
    start_year: 2025,
    end_year: 2026,
    status: "active",
  },
  {
    id: "ay2",
    branch_id: "br1",
    name: "2026-2027",
    start_year: 2026,
    end_year: 2027,
    status: "active",
  },
];

const MOCK_COURSES: CourseResponse[] = [
  {
    id: "c1",
    branch_id: "br1",
    name: "NEET 2-Year",
    code: "NEET-2Y",
    description: null,
    duration_years: 2,
    status: "active",
  },
  {
    id: "c2",
    branch_id: "br1",
    name: "Class 9",
    code: "C9",
    description: null,
    duration_years: 1,
    status: "active",
  },
];

describe("CreateBatchDialog", () => {
  const mockOnSubmit = vi.fn();
  const mockOnCreateYear = vi.fn();
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the trigger button", () => {
    render(
      withQuery(
        <CreateBatchDialog
          academicYears={MOCK_YEARS}
          courses={MOCK_COURSES}
          onSubmit={mockOnSubmit}
          onCreateAcademicYear={mockOnCreateYear}
          isPending={false}
        />
      )
    );

    expect(
      screen.getByRole("button", { name: /create batch/i })
    ).toBeInTheDocument();
  });

  it("shows form fields when dialog opens", async () => {
    render(
      withQuery(
        <CreateBatchDialog
          academicYears={MOCK_YEARS}
          courses={MOCK_COURSES}
          onSubmit={mockOnSubmit}
          onCreateAcademicYear={mockOnCreateYear}
          isPending={false}
        />
      )
    );

    await user.click(screen.getByRole("button", { name: /create batch/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/batch name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/batch code/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/capacity/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/course/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/start academic year/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/end academic year/i)).toBeInTheDocument();
    });
  });

  it("auto-computes end academic year for a 2-year course", async () => {
    render(
      withQuery(
        <CreateBatchDialog
          academicYears={MOCK_YEARS}
          courses={MOCK_COURSES}
          onSubmit={mockOnSubmit}
          onCreateAcademicYear={mockOnCreateYear}
          isPending={false}
        />
      )
    );

    await user.click(screen.getByRole("button", { name: /create batch/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/end academic year/i)).toBeInTheDocument();
    });

    const endInput = screen.getByLabelText(
      /end academic year/i
    ) as HTMLInputElement;
    // Defaults: course=NEET 2-Year (2 yr), start=2025-2026 → end=2026-2027
    expect(endInput.value).toBe("2026-2027");
  });

  it("submits with start_academic_year_id and course_id", async () => {
    mockOnSubmit.mockResolvedValue(undefined);

    render(
      withQuery(
        <CreateBatchDialog
          academicYears={MOCK_YEARS}
          courses={MOCK_COURSES}
          onSubmit={mockOnSubmit}
          onCreateAcademicYear={mockOnCreateYear}
          isPending={false}
        />
      )
    );

    await user.click(screen.getByRole("button", { name: /create batch/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/batch name/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/batch name/i), "NEET 2025-2027 A");
    await user.type(screen.getByLabelText(/batch code/i), "NEET-A");

    await user.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "NEET 2025-2027 A",
          code: "NEET-A",
          start_academic_year_id: "ay1",
          course_id: "c1",
        })
      );
    });
  });

  it("offers inline 'Create yyyy-yyyy academic year' button when end year is missing, and submit auto-creates it", async () => {
    mockOnSubmit.mockResolvedValue(undefined);
    mockOnCreateYear.mockResolvedValue({
      id: "ay3",
      branch_id: "br1",
      name: "2027-2028",
      start_year: 2027,
      end_year: 2028,
      status: "active",
    });

    // Only ay1 (2025-2026) and ay2 (2026-2027) exist; selecting ay2 + 2-year
    // course → end year would be 2027, which is missing.
    render(
      withQuery(
        <CreateBatchDialog
          academicYears={MOCK_YEARS}
          courses={MOCK_COURSES}
          onSubmit={mockOnSubmit}
          onCreateAcademicYear={mockOnCreateYear}
          isPending={false}
        />
      )
    );

    await user.click(screen.getByRole("button", { name: /create batch/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/start academic year/i)).toBeInTheDocument();
    });

    // Switch start year to 2026-2027 → end year target = 2027 (missing)
    await user.selectOptions(
      screen.getByLabelText(/start academic year/i),
      "ay2"
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /create 2027-2028 academic year/i })
      ).toBeInTheDocument();
    });

    // Fill in name and code, then submit — should auto-create the year
    await user.type(screen.getByLabelText(/batch name/i), "NEET 2026-2028 A");
    await user.type(screen.getByLabelText(/batch code/i), "NEET-A-2628");
    await user.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockOnCreateYear).toHaveBeenCalledWith(2027);
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "NEET 2026-2028 A",
          code: "NEET-A-2628",
          start_academic_year_id: "ay2",
          course_id: "c1",
        })
      );
    });
  });

  it("disables submit button when isPending", async () => {
    render(
      withQuery(
        <CreateBatchDialog
          academicYears={MOCK_YEARS}
          courses={MOCK_COURSES}
          onSubmit={mockOnSubmit}
          onCreateAcademicYear={mockOnCreateYear}
          isPending={true}
        />
      )
    );

    await user.click(screen.getByRole("button", { name: /create batch/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /creating/i })).toBeDisabled();
    });
  });
});
