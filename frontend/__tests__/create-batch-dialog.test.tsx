import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreateBatchDialog } from "@/app/(dashboard)/batches/_components/create-batch-dialog";
import type {
  AcademicYearResponse,
  CourseResponse,
} from "@/app/(dashboard)/batches/_schemas/batch";

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
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the trigger button", () => {
    render(
      <CreateBatchDialog
        academicYears={MOCK_YEARS}
        courses={MOCK_COURSES}
        onSubmit={mockOnSubmit}
        isPending={false}
      />
    );

    expect(
      screen.getByRole("button", { name: /create batch/i })
    ).toBeInTheDocument();
  });

  it("shows form fields when dialog opens", async () => {
    render(
      <CreateBatchDialog
        academicYears={MOCK_YEARS}
        courses={MOCK_COURSES}
        onSubmit={mockOnSubmit}
        isPending={false}
      />
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
      <CreateBatchDialog
        academicYears={MOCK_YEARS}
        courses={MOCK_COURSES}
        onSubmit={mockOnSubmit}
        isPending={false}
      />
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
      <CreateBatchDialog
        academicYears={MOCK_YEARS}
        courses={MOCK_COURSES}
        onSubmit={mockOnSubmit}
        isPending={false}
      />
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

  it("disables submit button when isPending", async () => {
    render(
      <CreateBatchDialog
        academicYears={MOCK_YEARS}
        courses={MOCK_COURSES}
        onSubmit={mockOnSubmit}
        isPending={true}
      />
    );

    await user.click(screen.getByRole("button", { name: /create batch/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /creating/i })).toBeDisabled();
    });
  });
});
